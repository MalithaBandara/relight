"""Checks that need no model call: the agent's fact check, the realtime line's noise guard and cached replays, the
portal upload endpoint and the speech synthesiser's latency. Safe to run any time (no API, no GO needed).

Usage:  python scripts/check_offline.py [--tts]      (--tts also times edge-tts; it needs internet)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from relight import config, realtime  # noqa: E402
from relight.callagent import facts_kept  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def fact_check() -> None:
    print("facts_kept (the agent's check on a reworded line)")
    # (draft, line, names to keep, expected dropped)
    cases = [
        ("restore 23 customers", "restore 23 customers", (), []),
        ("restore 23 customers", "restore 123 customers", (), ["23"]),
        ("houses 6 to 14", "houses 16 to 14", (), ["6"]),
        ("houses 6 to 14", "houses 6 to 16", (), ["14"]),
        ("around 15:20", "சுமார் 15:20 மணிக்கு", (), []),
        ("around 15:20", "around 5:20", (), ["15:20"]),
        ("number 52", "අංක 52 අසල", (), []),
        ("number 52", "अंक ५२", (), ["52"]),
        ("logged against I2", "සටහන් කළා I2 යටතේ", ("I2",), []),
        ("logged against I2", "logged against I20", ("I2",), ["2", "I2"]),
        ("logged against I2", "logged against I3", ("I2",), ["2", "I2"]),
        ("on Hospital Road", "Hospital Road ළඟ", ("Hospital Road",), []),
        ("on Hospital Road", "hospital road", ("Hospital Road",), []),
        ("on Hospital Road", "ஆஸ்பத்திரி ரோடு", ("Hospital Road",), ["Hospital Road"]),
    ]
    for draft, said, keep, want in cases:
        got = facts_kept(draft, said, keep)
        check(f"{draft!r} -> {said!r}", got == want, f"dropped={got}")


class FakeClient:
    mode = "live"

    def _key(self, kind: str, payload: dict) -> Path:
        return Path("unused")


async def noise_guard() -> None:
    print("realtime line: speech outside any utterance is never anyone's turn")
    got: list[dict] = []

    async def on_event(ev: dict) -> None:
        got.append(ev)

    line = realtime.Line(FakeClient(), "T1", "en", on_event=on_event)
    line._spans.append((1000, 3000, "caller"))
    for m in ({"type": "speechStart", "turnId": 1, "audioProcessedMs": 1200},
              {"type": "transcript", "transcript": "The power is out", "audioProcessedMs": 2200},
              {"type": "speechComplete", "turnId": 1, "transcript": "The power is out", "audioProcessedMs": 3000},
              {"type": "speechStart", "turnId": 2, "audioProcessedMs": 9000},   # nobody on the line
              {"type": "transcript", "transcript": "Yeah", "audioProcessedMs": 9300},
              {"type": "speechComplete", "turnId": 2, "transcript": "Yeah", "audioProcessedMs": 9600}):
        await line._server(m)
    finals = [e for e in got if e["kind"] == "final"]
    check("speech inside the utterance is attributed to the caller", finals[0]["role"] == "caller")
    check("speech with nobody on the line is labelled unknown", finals[1]["role"] == "unknown")
    # play() takes a final only if its start falls inside the utterance window
    window = (1000 - 300, 3000)
    check("play() would drop the stray turn", not (window[0] <= finals[1]["start"] <= window[1]))


async def cached_replays() -> None:
    print("realtime: cached sessions replay in order, at the recorded pace")
    realtime.SPEED = 20.0
    files = sorted((config.ROOT / ".cache" / "model").glob("asr-rt-*.json"))
    check("cached realtime sessions found", bool(files), f"{len(files)} files")
    bad_order = bad_text = bad_count = 0
    gaps: list[float] = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        ats = [e["at"] for e in data["events"]]
        bad_order += ats != sorted(ats)  # recorded times must not go backwards
        gaps += [b - a for a, b in zip(ats, ats[1:]) if b > a]
        finals = [e["text"] for e in data["events"] if e["kind"] == "final"]
        bad_text += not (finals and finals[-1].strip() and data["text"].strip().startswith(finals[0].strip()[:20]))
        seen: list[dict] = []

        async def on_event(ev: dict, seen=seen) -> None:
            seen.append(ev)

        line = realtime.Line(FakeClient(), "T", "en", on_event=on_event)
        t0 = time.monotonic()
        await line._replay(data["events"], data["events"][0]["role"] if data["events"] else "caller",
                           max(ats + [0.1]) / realtime.SPEED)  # play() divides the clip length by SPEED too
        bad_count += len(seen) != len(data["events"])
        slow = time.monotonic() - t0 - max(ats + [0.1]) / realtime.SPEED
        bad_order += slow > 0.5
    check("events are in time order and replay at the recorded pace", bad_order == 0, f"{bad_order} sessions off")
    check("every event is delivered", bad_count == 0, f"{bad_count} sessions short")
    check("final text matches the session text", bad_text == 0, f"{bad_text} sessions differ")
    if gaps:
        gaps.sort()
        print(f"       gap between events: median {gaps[len(gaps) // 2]:.2f}s, max {gaps[-1]:.2f}s "
              f"(live partials were ~0.3 s apart)")


def uploads() -> None:
    print("portal upload endpoint")
    from fastapi.testclient import TestClient

    from relight import server

    c = TestClient(server.app)
    made: list[Path] = []

    def post(data: bytes, ctype: str, name: str = "x"):
        r = c.post("/api/customer/upload", files={"file": (name, data, ctype)})
        if r.status_code == 200:
            made.append(ROOT / r.json()["path"])
        return r

    r = post(b"\xff\xd8\xff" + b"0" * 1000, "image/jpeg", "a.jpg")
    check("small JPEG accepted as a photo", r.status_code == 200 and r.json()["kind"] == "photo", r.text[:80])
    r = post(b"\x00\x00\x00\x14ftypqt  " + b"1" * 5000, "video/quicktime", "IMG_0001.MOV")
    check("iPhone MOV accepted as a video", r.status_code == 200 and r.json()["kind"] == "video"
          and r.json()["path"].endswith(".mov"), r.text[:80])
    r = post(b"2" * (50 * 1024 * 1024), "video/mp4", "big.mp4")
    check("50 MB MP4 accepted", r.status_code == 200, f"{r.status_code}")
    r = post(b"3" * (60 * 1024 * 1024 + 1), "video/mp4", "huge.mp4")
    check("60 MB + 1 byte refused with 413 and a plain message", r.status_code == 413 and "60 MB" in r.text,
          r.text[:80])
    r = post(b"hello", "text/plain", "n.txt")
    check("a text file is refused with 415", r.status_code == 415, r.text[:80])
    r = post(b"4" * 100, "image/heic", "p.heic")
    check("HEIC (iPhone photo default) is refused with 415", r.status_code == 415, "see note below")
    for p in made:
        p.unlink(missing_ok=True)
    c.close()


def drone_survey_check() -> None:
    print("drone survey (counted from the cached SAM 3.1 tracks of the Temple Road clip)")
    from relight import vision
    from relight.models import ModelClient

    clip = ROOT / "media" / "drone" / "temple_road_span.mp4"
    if not clip.exists():
        print("  skipped: drone clip not on this computer (scripts/fetch_videos.py)")
        return
    res = vision.analyse_video(ModelClient(), clip.relative_to(ROOT).as_posix(), "tree_on_line", "drone")
    s = res.get("survey")
    if s is None:
        print("  skipped: no cached SAM tracks (needs a live run once)")
        return
    check("3 poles followed, none lying", s["poles"] == {"followed": 3, "lying": 0}, str(s["poles"]))
    check("wires followed are fewer than the pieces SAM split them into", 0 < s["wires"]["followed"] < s["wires"]["pieces"],
          str(s["wires"]))
    check("the fallen trunk is found crossing wires", s["obstructions"] and s["obstructions"][0]["wires_crossed"] > 0,
          "; ".join(s["flags"]))
    # a lying pole and an obstruction that crosses nothing, from hand-made tracks
    box = lambda x1, y1, x2, y2: (x1, y1, x2, y2)  # noqa: E731
    fr = lambda b, n=10: [{"frame": i, "id": 0, "box": b} for i in range(n)]  # noqa: E731
    t = vision.drone_survey({"utility pole": fr(box(0, 0, 100, 50)), "power line": fr(box(0, 200, 800, 220)),
                             "tree": fr(box(0, 0, 800, 100))})
    check("a pole box wider than tall is reported lying", t["poles"]["lying"] == 1)
    check("a tree above the wire crosses nothing", t["obstructions"][0]["wires_crossed"] == 0)


def mask_checks() -> None:
    print("SAM masks: decoder, lean, sag, contact (hand-made masks, and the cached drone clip)")
    import glob

    from relight import masks
    from relight.masks import Mask

    def bar(x, y, w, h, cells=None):
        data = bytearray(w * h)
        for cx, cy in (cells or [(i, j) for j in range(h) for i in range(w)]):
            data[cy * w + cx] = 1
        return Mask(x, y, w, h, bytes(data))

    upright = masks.lean_deg(bar(0, 0, 4, 80))
    check("a standing bar leans ~0 degrees", upright is not None and abs(upright) < 2, str(upright))
    diag = bar(0, 0, 60, 60, [(i + d, i) for i in range(56) for d in range(3)])
    check("a diagonal bar leans ~45 degrees", abs((masks.lean_deg(diag) or 0) - 45) < 4)
    check("a lying bar leans ~90 degrees", (masks.lean_deg(bar(0, 0, 80, 4)) or 0) > 85)
    check("a blob (pole seen from above) has no lean", masks.lean_deg(bar(0, 0, 40, 40)) is None)
    flat = bar(0, 0, 100, 30, [(x, 10) for x in range(100)])
    check("a flat wire has no sag", (masks.sag_ratio(flat) or 0) < 0.005, str(masks.sag_ratio(flat)))
    sag = bar(0, 0, 100, 40, [(x, 10 + int(20 * (1 - ((x - 50) / 50) ** 2))) for x in range(100)])
    check("a wire dropping 20 px over 100 px sags ~20%", abs((masks.sag_ratio(sag) or 0) - 0.2) < 0.03, str(masks.sag_ratio(sag)))
    check("crossing bars touch", masks.touches(bar(0, 10, 50, 3), bar(20, 0, 3, 40)))
    check("separate bars do not", not masks.touches(bar(0, 10, 50, 3), bar(20, 20, 3, 20)))
    check("flags: a wire sagging 3x the median is named",
          any("sags" in f for f in masks.flags({"poles": [], "wires_long": 4, "obstructions": [], "median_sag": 0.01,
              "wires": [{"id": "a", "sag": 0.01}, {"id": "b", "sag": 0.01}, {"id": "c", "sag": 0.01},
                        {"id": "d", "sag": 0.05}]})))
    check("flags: a 30 degree pole is named",
          any("leans" in f for f in masks.flags({"poles": [{"id": "p", "lean_deg": 30.0, "frames": 3}], "wires": [],
                                                 "wires_long": 0, "obstructions": []})))
    clip = ROOT / "media" / "drone" / "temple_road_span.mp4"
    cached = glob.glob(str(ROOT / ".cache" / "masks" / "*.pkl"))
    if clip.exists() and cached:
        from relight import vision
        from relight.models import ModelClient
        res = vision.analyse_video(ModelClient(), clip.relative_to(ROOT).as_posix(), "tree_on_line", "drone")
        m = ((res.get("survey") or {}).get("masks")) or {}
        check("drone clip: trunk touches wires by pixel overlap", any(o["wires_touched"] for o in m.get("obstructions", [])),
              "; ".join((res.get("survey") or {}).get("flags", [])))
        check("drone clip: top-down pole not reported as leaning", all(p["lean_deg"] < masks.LEAN_FLAG_DEG for p in m.get("poles", [])))
        check("drone clip: outlines video built", bool(res.get("overlay")), str(res.get("overlay")))
    else:
        print("  skipped the drone checks: run scripts/build_overlays.py once (needs the clip and its cached SAM response)")


class FakeSpark:
    """Stands in for ModelClient: SAM finds one plate, Spark reads it with the usual OCR slip."""
    def __init__(self, tag, readable=True, plates=True):
        self.tag, self.readable, self.plates = tag, readable, plates

    def segment_image(self, path, prompt, confidence=True):
        return [{"box": (40.0, 60.0, 110.0, 90.0), "conf": 0.9, "w": 200, "h": 150}] if self.plates else []

    def spark_json(self, system, user, schema, name, **kw):
        return {"readable": self.readable, "tag": self.tag, "confidence": "high", "note": ""}


def pole_tags() -> None:
    print("pole tags: SAM finds the plate, Spark reads it, the register names the pole")
    from PIL import Image

    from relight import grid, packs, vision
    from relight.poles import PoleRegister

    img = ROOT / "media" / "uploads" / "_tag_test.jpg"
    img.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 150), (90, 90, 90)).save(img)
    try:
        feeder, _ = packs.network(json.loads((ROOT / "scenarios" / "galle_storm.json").read_text(encoding="utf-8")))
        reg = PoleRegister(feeder)
        pole = list(reg.poles.values())[100]
        rel = img.relative_to(ROOT).as_posix()
        r = vision.read_pole_tag(FakeSpark(pole.tag.replace("0", "O")), rel)
        check("plate read through SAM box and Spark crop", r and r["tag"] and r["models"] == ["SAM 3.1", "Muse Spark"]
              and r["crop"] and r["box"], str(r and r["tag"]))
        got, how = reg.lookup(r["tag"])
        check("an O for a 0 still finds the pole, and says so", got is pole and how == "OCR-tolerant", how)
        check("the exact tag matches exactly", reg.lookup(pole.tag) == (pole, "exact"))
        check("an unknown tag names no pole", reg.lookup("ZZ-9999")[0] is None)
        check("an unreadable plate gives no tag", vision.read_pole_tag(FakeSpark(None, False), rel)["tag"] is None)
        check("no plate found by SAM and Spark unreadable gives nothing",
              vision.read_pole_tag(FakeSpark(None, False, plates=False), rel) is None)
        check("mock mode returns the scenario's tag", vision.read_pole_tag(type("N", (), {
            "segment_image": lambda *a, **k: None})(), rel, "P-0007")["tag"] == "P-0007")
        a = grid.haversine_m((pole.lat, pole.lon), (feeder.point_on_section(pole.section, pole.offset_m)))
        check("the pole sits on its section", a < 1.0, f"{a:.2f} m")
    finally:
        img.unlink(missing_ok=True)
        for f in (ROOT / "media" / "uploads").glob("tag_*.jpg"):
            f.unlink(missing_ok=True)


async def pole_tag_in_engine() -> None:
    print("pole tag moves a customer photo's damage to the exact pole")
    from relight.engine import Engine
    from relight.scenario import Replayer, load

    sc = load("galle_storm")
    quiet = lambda _m: asyncio.sleep(0)  # noqa: E731
    probe = Engine(sc, quiet)
    c18 = next(e for e in sc["events"] if e.get("id") == "C18")
    cust = probe.db.by_address(c18["truth"]["street"], c18["truth"]["house_no"])[0]
    # a pole about 150 m from the caller, so the move is visible
    far = min(probe.poles.poles.values(), key=lambda p: abs(grid_m(p, cust) - 150))
    c18["media_pole_tag"] = far.tag.replace("0", "O")
    engine = Engine(sc, quiet)
    replayer = Replayer(sc, engine.handle)
    engine.sim = replayer
    while replayer.queue and replayer.queue[0][0] <= 760:
        import heapq
        _, _, e = heapq.heappop(replayer.queue)
        await replayer.deliver(e)
    item = next((m for m in engine.media if m["ref"] == "C18"), None)
    check("the photo was analysed", item is not None)
    tag = (item or {}).get("analysis", {}).get("pole_tag") or {}
    check("the tag was matched to the pole", tag.get("pole", {}).get("id") == far.id, str(tag.get("match")))
    check("the marker moved to the pole", item and abs(item["lat"] - far.lat) < 1e-9 and abs(item["lon"] - far.lon) < 1e-9)
    check("the timeline names the pole", any("pole tag" in t["title"] and far.id in t["detail"] for t in engine.timeline))
    check("the photo counts as strong damage evidence", any(d.strength >= 4.0 and d.source == "C18/photo"
                                                            for d in engine.field_damage))


def grid_m(p, cust) -> float:
    from relight.grid import haversine_m
    return haversine_m((p.lat, p.lon), (cust.lat, cust.lon))


async def tts_latency() -> None:
    print("edge-tts latency (the World's site reports are spoken before transcription in live mode)")
    from relight import voice

    if not voice.available():
        print("  skipped: edge-tts or ffmpeg missing")
        return
    lines = [("en-US-GuyNeural", "Crew at number 55 Cinnamon Gardens Lane near transformer T-093. The drop-out fuse is "
              "blown and is being replaced."),
             ("en-US-GuyNeural", "Pole down at Hospital Road near number 52. Need a line crew and a bucket truck.")]
    for i, (v, t) in enumerate(lines):
        out = ROOT / "media" / "audio" / "tts" / f"_latency_{i}.wav"
        t0 = time.monotonic()
        await voice.synthesize(t, v, out=out)
        dt = time.monotonic() - t0
        out.unlink(missing_ok=True)
        check(f"{len(t.split())}-word report spoken", dt < 6, f"{dt:.1f}s")


async def main() -> None:
    fact_check()
    await noise_guard()
    await cached_replays()
    uploads()
    drone_survey_check()
    mask_checks()
    pole_tags()
    await pole_tag_in_engine()
    if "--tts" in sys.argv:
        await tts_latency()
    print("\nALL OK" if not failures else f"\n{len(failures)} FAILED: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
