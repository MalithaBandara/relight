"""FastAPI app: serves the map UI, the grid, and a WebSocket stream of the live triage.

Run with:  python -m uvicorn relight.server:app --reload
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from . import packs
from . import voice
from .crewreport import CrewReport
from .engine import Engine, clock_str
from .portalcall import PortalCall
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
portal_calls: dict[str, PortalCall] = {}  # customers on a call from the portal (cleared with the engine)
crew_reports: dict[str, CrewReport] = {}  # reports from the crew page, until they are filed


async def handle(e: dict) -> None:
    async with lock:
        await engine.handle(e)


def open_scenario(name: str) -> None:
    """Build the engine and simulated world for one scenario (network and customers are cached)."""
    global scenario, engine, replayer
    portal_calls.clear()
    crew_reports.clear()
    scenario = load(name)
    engine = Engine(scenario, broadcast)
    replayer = Replayer(scenario, handle)
    engine.sim = replayer
    engine.lock = lock


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
    action: str  # start | pause | reset | speed | live_calls | handover
    speed: float | None = None
    on: bool | None = None


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
    elif c.action in ("live_calls", "handover"):
        # Live calls play voiced calls in real time (the storm waits while one is on the line).
        setattr(engine, c.action, bool(c.on))
        await broadcast({"type": "live", "calls": engine.live_calls, "handover": engine.handover})
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
    media: str = ""  # path returned by /api/customer/upload


UPLOAD_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
                "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}
UPLOAD_MAX = 60 * 1024 * 1024


@app.post("/api/customer/upload")
async def customer_upload(file: UploadFile = File(...)):
    """A photo or short video attached to a portal report; stored under media/uploads (git-ignored)."""
    ext = UPLOAD_TYPES.get(file.content_type or "")
    if ext is None:
        return JSONResponse({"error": "Send a photo (JPG, PNG) or a video (MP4, MOV, WebM)."}, status_code=415)
    data = await file.read(UPLOAD_MAX + 1)
    if len(data) > UPLOAD_MAX:
        return JSONResponse({"error": "That file is over 60 MB. Send a shorter video."}, status_code=413)
    rel = f"media/uploads/{hashlib.sha256(data).hexdigest()[:16]}{ext}"
    (config.ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (config.ROOT / rel).write_bytes(data)
    return {"path": rel, "kind": "video" if ext in (".mp4", ".mov", ".webm") else "photo"}


@app.post("/api/customer/report")
async def customer_report(r: Report):
    """A complaint typed live into the customer portal, processed like any other message."""
    c = engine.db.by_account(r.who) or engine.db.by_phone(r.who)
    n = sum(m["channel"] == "web" for m in engine.messages) + 1
    e = {"t": max(replayer.clock, engine.elapsed), "type": "complaint", "id": f"W{n}", "channel": "web",
         "language": r.language, "from": c.phone if c else (r.who or None), "text": r.text, "truth": {}}
    media = Path(r.media)
    if len(media.parts) == 3 and media.parts[:2] == ("media", "uploads") and (config.ROOT / media).is_file():
        e["video" if media.suffix in (".mp4", ".mov", ".webm") else "photo"] = media.as_posix()
    await handle(e)
    msg = next((m for m in reversed(engine.messages) if m["id"] == e["id"]), None)
    return {"message": {k: v for k, v in (msg or {}).items() if k != "event"},
            "status": engine.customer_status(c.account_no) if c else None}


class CallStart(BaseModel):
    who: str = ""  # account number or phone (optional: the agent asks for the address)
    language: str = "en"


@app.post("/api/customer/call")
async def customer_call(r: CallStart):
    """A customer rings the outage desk from the portal: the call agent greets them."""
    for old in [k for k, c in portal_calls.items() if c.done]:
        portal_calls.pop(old)
    n = sum(m["id"].startswith("PC") for m in engine.messages) + len(portal_calls) + 1
    pc = PortalCall(engine, f"PC{n}", r.who, r.language, max(replayer.clock, engine.elapsed))
    portal_calls[pc.id] = pc
    return await pc.start()


@app.post("/api/customer/call/{call_id}/say")
async def customer_call_say(call_id: str, audio: UploadFile | None = File(None), text: str = Form("")):
    """One thing the caller says: a short WAV (16 kHz mono) from the microphone, or typed words."""
    pc = portal_calls.get(call_id)
    if pc is None:
        return JSONResponse({"error": "That call has ended. Start a new one."}, status_code=410)
    wav = await audio.read(7 * 1024 * 1024) if audio is not None else None
    return await pc.say(wav, text)


@app.post("/api/customer/call/{call_id}/end")
async def customer_call_end(call_id: str):
    pc = portal_calls.get(call_id)
    if pc is None:
        return JSONResponse({"error": "That call has ended."}, status_code=410)
    return await pc.hang_up()


@app.get("/api/crews")
def crews():
    """The crews of this scenario and what each is doing, for the crew page."""
    lang = {c["id"]: c.get("language", "en") for c in scenario["crews"]}
    out = []
    for c in engine.crews.values():
        inc = engine._incident(c["incident"])
        out.append({"id": c["id"], "name": c["name"], "skills": sorted(c["skills"]), "language": lang.get(c["id"], "en"),
                    "status": c["status"], "task": c.get("step"),
                    "incident": {"id": inc["id"], "title": inc["title"], "label": inc["label"]} if inc else None})
    return {"crews": out, "languages": packs.pack(scenario).get("languages") or ["en"],
            "scenario": scenario["id"], "clock": engine.clock(max(replayer.clock, engine.elapsed))}


def _media_path(path: str) -> str | None:
    media = Path(path)
    if len(media.parts) == 3 and media.parts[:2] == ("media", "uploads") and (config.ROOT / media).is_file():
        return media.as_posix()
    return None


@app.post("/api/crew/report")
async def crew_report(crew_id: str = Form(...), language: str = Form(""), text: str = Form(""), media: str = Form(""),
                      audio: UploadFile | None = File(None)):
    """A crew files a report from the crew page: the agent reads back what it understood and waits for the crew."""
    crew = engine.crews.get(crew_id)
    if crew is None:
        return JSONResponse({"error": "That crew is not part of this scenario."}, status_code=404)
    lang = language or next((c.get("language", "en") for c in scenario["crews"] if c["id"] == crew_id), "en")
    n = sum(m["id"].startswith("CR") for m in engine.messages) + len(crew_reports) + 1
    cr = CrewReport(engine, f"CR{n}", crew, lang, max(replayer.clock, engine.elapsed), _media_path(media))
    wav = await audio.read(7 * 1024 * 1024) if audio is not None else None
    out = await cr.begin(wav, text)
    if out.get("id"):
        crew_reports[cr.id] = cr
    return out


@app.post("/api/crew/report/{rid}/answer")
async def crew_answer(rid: str, ok: str = Form("true"), text: str = Form(""), audio: UploadFile | None = File(None)):
    """The crew's reply to the read-back: correct, or a corrected report."""
    cr = crew_reports.get(rid)
    if cr is None:
        return JSONResponse({"error": "That report is already filed or the scenario was changed."}, status_code=410)
    wav = await audio.read(7 * 1024 * 1024) if audio is not None else None
    out = await cr.answer(ok.lower() in ("true", "1", "yes"), wav, text)
    if cr.done:
        crew_reports.pop(rid, None)
    return out


@app.get("/crew")
def crew_page():
    return FileResponse(config.WEB_DIR / "crew.html")


class CopilotAction(BaseModel):
    id: str
    action: str  # say | file | end
    act: str | None = None  # one of the copilot's options (say)
    text: str | None = None  # the call-taker's own words (say)


@app.post("/api/copilot")
async def copilot(a: CopilotAction):
    """The call-taker's buttons. Speaking takes seconds, so it runs in the background; state comes over /ws."""
    cp = engine.copilots.get(a.id)
    if cp is None:
        return {"ok": False, "error": "no call-taker session for that call"}
    if a.action == "say":
        if cp.busy:
            return {"ok": False, "error": "wait for the caller to finish"}
        asyncio.create_task(cp.say(a.act, (a.text or "").strip() or None))
        return {"ok": True}
    if a.action == "file":
        return await cp.file()
    if a.action == "end":
        return await cp.end()
    return {"ok": False, "error": "unknown action"}


@app.websocket("/ws/mic/{call_id}")
async def mic(websocket: WebSocket, call_id: str):
    """The call-taker's microphone: 24 kHz mono 16-bit PCM frames, mixed into the call's realtime line."""
    await websocket.accept()
    cp = engine.copilots.get(call_id)
    try:
        while True:
            data = await websocket.receive_bytes()
            if cp is None or not cp.mic(data):
                await websocket.send_text(json.dumps({"error": "The microphone needs the live realtime line "
                                                      "(Meta API key and approval); type your line instead."}))
                await websocket.close()
                return
    except WebSocketDisconnect:
        pass


@app.get("/api/call/{msg_id}/{turn}.wav")
async def call_audio(msg_id: str, turn: int):
    """One line of an agent call as audio: the caller's recording, or speech synthesised on first request."""
    m = next((m for m in engine.messages if m["id"] == msg_id and "call" in m), None)
    call = m["call"] if m else engine.agent.live.get(msg_id)  # a live call still on the line
    if call is None and msg_id in portal_calls:
        call = portal_calls[msg_id].call
    if call is None and msg_id in crew_reports:  # a crew's read-back that is waiting for their answer
        call = crew_reports[msg_id].call
    if call is None or not 0 <= turn < len(call["turns"]):
        return JSONResponse({"error": "no such call line"}, status_code=404)
    line = call["turns"][turn]
    if line.get("audio") and (config.ROOT / line["audio"]).exists():
        return FileResponse(config.ROOT / line["audio"], media_type="audio/wav")
    try:
        path = await voice.synthesize(line["text"], call["voices"][line["who"]])
    except Exception as err:  # noqa: BLE001 - no edge-tts / ffmpeg / network: the console shows text only
        return JSONResponse({"error": str(err)[:200]}, status_code=503)
    return FileResponse(path, media_type="audio/wav")


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
