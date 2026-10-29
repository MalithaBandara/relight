"""FastAPI app: serves the map UI, the grid, and a WebSocket stream of the live triage.

Run with:  python -m uvicorn gridmedic.server:app --reload
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
from .customers import CustomerDB
from .diagram import read_diagram, render_diagram, score
from .engine import Engine
from .grid import get_feeder
from .scenario import Replayer, load

app = FastAPI(title="GridMedic")
clients: set[WebSocket] = set()


async def broadcast(msg: dict) -> None:
    data = json.dumps(msg, ensure_ascii=False, default=list)
    for ws in list(clients):
        try:
            await ws.send_text(data)
        except Exception:
            clients.discard(ws)


scenario = load()
replayer: Replayer
engine = Engine(scenario, broadcast, on_probe=lambda p: replayer.schedule_probe_reply(p))
replayer = Replayer(scenario, engine.handle)


async def tick(clock: float) -> None:
    await broadcast({"type": "clock", "elapsed": round(clock), "speed": replayer.speed,
                     "running": replayer.running, "duration": scenario["duration_s"]})


class Control(BaseModel):
    action: str  # start | pause | reset | speed | offline | online
    speed: float | None = None


@app.post("/api/control")
async def control(c: Control):
    if c.speed:
        replayer.speed = c.speed
    if c.action == "start" and not replayer.running:
        replayer.task = asyncio.create_task(replayer.run(tick))
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


@app.get("/api/grid")
def grid():
    db = CustomerDB()
    feeder = get_feeder()
    return {
        "geojson": feeder.to_geojson(),
        "landmarks": db.landmarks,
        "crews": [{**c, "lat": feeder.bus_pos[c["base"]][0], "lon": feeder.bus_pos[c["base"]][1]}
                  for c in scenario["crews"]],
        "substation": feeder.bus_pos["800"],
        "customers": db.counts_by_transformer(),
        "title": scenario["title"],
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
