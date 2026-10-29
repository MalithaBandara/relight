"""FastAPI app: serves the map UI, the grid, and a WebSocket stream of the live triage.

Run with:  python -m uvicorn relight.server:app --reload
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from . import packs
from .diagram import read_diagram, render_diagram, score
from .engine import Engine, clock_str
from .scenario import Replayer, load

app = FastAPI(title="Relight")
clients: set[WebSocket] = set()


async def broadcast(msg: dict) -> None:
    data = json.dumps(msg, ensure_ascii=False, default=list)
    for ws in list(clients):
        try:
            await ws.send_text(data)
        except Exception:
            clients.discard(ws)


lock = asyncio.Lock()  # one writer at a time: the replay, the operator, the customer portal


async def handle(e: dict) -> None:
    async with lock:
        await engine.handle(e)


def open_scenario(name: str) -> None:
    """Build the engine and simulated world for one scenario (network and customers are cached)."""
    global scenario, engine, replayer
    scenario = load(name)
    engine = Engine(scenario, broadcast)
    replayer = Replayer(scenario, handle)
    engine.sim = replayer


def list_scenarios() -> list[dict]:
    out = []
    for p in sorted(config.SCENARIO_DIR.glob("*.json")):
        sc = json.loads(p.read_text(encoding="utf-8"))
        pk = packs.pack(sc)
        out.append({"id": p.stem, "title": sc["title"], "country": packs.locale(sc)["country"],
                    "smart_meters": bool(pk.get("smart_meters")), "network": pk["network"]["type"]})
    order = {"galle_storm": 0, "houston_hurricane": 1, "chennai_cyclone": 2}
    return sorted(out, key=lambda s: order.get(s["id"], 9))


open_scenario("galle_storm")


async def tick(clock: float) -> None:
    async with lock:
        await engine.advance(clock)
    await broadcast({"type": "clock", "elapsed": round(clock), "clock": engine.clock(clock), "speed": replayer.speed,
                     "running": replayer.running, "duration": scenario["duration_s"], "timelapse": replayer.timelapse,
                     "crews": engine.crew_positions()})


class Control(BaseModel):
    action: str  # start | pause | reset | speed | offline | online
    speed: float | None = None


class ScenarioChoice(BaseModel):
    id: str


@app.get("/api/scenarios")
def scenarios():
    return {"current": scenario["id"], "scenarios": list_scenarios()}


@app.post("/api/scenario")
async def choose_scenario(c: ScenarioChoice):
    if c.id not in {s["id"] for s in list_scenarios()}:
        return {"ok": False}
    replayer.running = False
    await asyncio.sleep(0.2)
    async with lock:
        await asyncio.to_thread(open_scenario, c.id)
    await broadcast({"type": "scenario", "id": c.id})
    return {"ok": True}


@app.post("/api/control")
async def control(c: Control):
    if c.speed:
        replayer.speed = c.speed
    if c.action == "start" and not replayer.running:
        replayer.task = asyncio.create_task(replayer.run(tick, engine.busy))
    elif c.action == "pause":
        replayer.running = False
    elif c.action in ("offline", "online"):
        await engine.set_offline(c.action == "offline")
    elif c.action == "reset":
        replayer.running = False
        if replayer.task:
            await asyncio.sleep(0.2)
        replayer.reset()
        engine.reset()
        await broadcast({"type": "reset"})
    await tick(replayer.clock)
    return {"ok": True, "running": replayer.running, "speed": replayer.speed}


class PlanChoice(BaseModel):
    incident: str
    plan: str


@app.post("/api/plan")
async def apply_plan(p: PlanChoice):
    async with lock:
        return await engine.apply_plan(p.incident, p.plan)


@app.get("/api/customer")
def customer(q: str):
    return engine.customer_status(q)


class Report(BaseModel):
    text: str
    who: str = ""  # account number or phone
    language: str = "en"


@app.post("/api/customer/report")
async def customer_report(r: Report):
    """A complaint typed live into the customer portal, processed like any other message."""
    c = engine.db.by_account(r.who) or engine.db.by_phone(r.who)
    n = sum(m["channel"] == "web" for m in engine.messages) + 1
    e = {"t": max(replayer.clock, engine.elapsed), "type": "complaint", "id": f"W{n}", "channel": "web",
         "language": r.language, "from": c.phone if c else (r.who or None), "text": r.text, "truth": {}}
    await handle(e)
    msg = next((m for m in reversed(engine.messages) if m["id"] == e["id"]), None)
    return {"message": {k: v for k, v in (msg or {}).items() if k != "event"},
            "status": engine.customer_status(c.account_no) if c else None}


@app.get("/customer")
def customer_page():
    return FileResponse(config.WEB_DIR / "customer.html")


@app.get("/api/grid")
def grid():
    feeder, db = engine.feeder, engine.db
    pk = packs.pack(scenario)
    return {
        "id": scenario["id"],
        "geojson": feeder.to_geojson(),
        "landmarks": db.landmarks,
        "crews": [{**c, "lat": feeder.bus_pos[c["base"]][0], "lon": feeder.bus_pos[c["base"]][1]}
                  for c in scenario["crews"]],
        "substation": feeder.bus_pos[feeder.root],
        "substation_label": feeder.substation_label,
        "customers": db.counts_by_transformer(),
        "title": scenario["title"],
        "country": packs.locale(scenario)["country"],
        "network": pk["network"]["type"],
        "start_hour": pk["start_hour"],
        "duration": scenario["duration_s"],
    }


DIAGRAM = config.MEDIA_DIR / "diagrams" / "feeder1_sld.png"


@app.post("/api/diagram")
async def diagram(image: UploadFile | None = File(None)):
    """Digitise a photographed single-line diagram and score it against the known feeder."""
    path = DIAGRAM
    if image is not None:
        path = config.MEDIA_DIR / "diagrams" / f"upload-{Path(image.filename or 'map.jpg').name}"
        path.write_bytes(await image.read())
    elif not path.exists():
        render_diagram(path)
    topo, model = await asyncio.to_thread(read_diagram, engine.client, path)
    result = score(topo)
    await engine.log(model, "Paper map digitised into the grid model",
                     f"{result['connections_correct']}/{result['connections_total']} connections, "
                     f"{result['devices_correct']}/{result['devices_total']} protective devices correct")
    return {"model": model, "image": "/" + path.relative_to(config.ROOT).as_posix(), "score": result,
            "topology": topo}


@app.get("/api/state")
def state():
    return engine.snapshot()


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_text(json.dumps({"type": "snapshot", "state": engine.snapshot()}, ensure_ascii=False,
                                         default=list))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)


config.MEDIA_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=config.MEDIA_DIR), name="media")
app.mount("/static", StaticFiles(directory=config.WEB_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.WEB_DIR / "index.html")
