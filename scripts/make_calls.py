"""Generate the voiced customer calls listed in scenarios/calls/<scenario>.json.

Nobody records these by hand: each caller's opening words are spoken by a neural text-to-speech voice (edge-tts)
and shaped like a phone line (relight/voice.py), giving media/audio/calls/<scenario>/<id>.wav. The words are a
spoken version of a complaint that already exists in the scenario, so its `truth` labels still hold and Voice
Transcribe + Spark can be scored against them. All callers are fictional; say so wherever the audio is played.
The agent's side of each call is synthesised on demand by the server, from what the agent decides live.

Media generation only:
    .venv/Scripts/pip install edge-tts      # needs ffmpeg on PATH
    .venv/Scripts/python scripts/make_calls.py [scenario ...] [--force]
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import voice  # noqa: E402
from relight.config import ROOT, SCENARIO_DIR  # noqa: E402
from relight.scenario import load  # noqa: E402


async def main(names: list[str], force: bool) -> None:
    if not voice.available():
        sys.exit("needs edge-tts (pip install edge-tts) and ffmpeg on PATH")
    names = names or [p.stem for p in sorted((SCENARIO_DIR / "calls").glob("*.json"))]
    for name in names:
        events = {e["id"]: e for e in load(name)["events"] if e.get("audio")}
        for cid in json.loads((SCENARIO_DIR / "calls" / f"{name}.json").read_text(encoding="utf-8"))["calls"]:
            e = events.get(cid)
            if e is None:
                print(f"{name} {cid}: no such complaint, skipped")
                continue
            out = ROOT / e["audio"]
            if out.exists() and not force:
                continue
            await voice.synthesize(e["text"], e["voice"], e.get("rate", "+0%"), out=out)
            print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main([a for a in args if not a.startswith("--")], "--force" in args))
