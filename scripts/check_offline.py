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
    if "--tts" in sys.argv:
        await tts_latency()
    print("\nALL OK" if not failures else f"\n{len(failures)} FAILED: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
