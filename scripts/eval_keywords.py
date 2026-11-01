"""Does Voice Transcribe hear street names better when it is given the feeder's street names as `keywords`?

Runs every voiced call and crew report in the scenarios (those in languages Voice Transcribe covers) twice, without and
with the keywords, and counts the clips whose transcript contains the street the caller named. The clips are synthetic
phone-quality speech (edge-tts), so the numbers show the effect, not real-world accuracy. Needs the API (GO): each
clip is a few seconds of audio ($0.18 per hour). Writes eval/keywords-<scenario>.json.

Usage:  python scripts/eval_keywords.py [scenario ...]      (default: all three)
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import config, packs  # noqa: E402
from relight.callagent import TRANSCRIBE_LANGS  # noqa: E402
from relight.models import ModelClient, fit_keywords  # noqa: E402
from relight.realtime import BIAS, MAX_KEYWORDS  # noqa: E402
from relight.scenario import load  # noqa: E402

WORKERS = 6
SAYS_STREET: set[str] = set()  # clips that name the street in words the script does not spell the same way


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def keywords_for(db) -> list[str]:
    """The same list the realtime line uses: landmarks, then streets with the most customers."""
    rows = db.con.execute("SELECT street, COUNT(*) n FROM customers GROUP BY street ORDER BY n DESC")
    names = [lm["name"] for lm in db.landmarks][:20] + [r[0] for r in rows]
    return fit_keywords(names, MAX_KEYWORDS)


def main() -> None:
    client = ModelClient(mode="live")
    if not config.MODEL_API_KEY:
        sys.exit("MODEL_API_KEY is not set.")
    names = sys.argv[1:] or ["galle_storm", "houston_hurricane", "chennai_cyclone"]
    out_dir = config.ROOT / "eval"
    out_dir.mkdir(exist_ok=True)
    grand = {"plain": [0, 0], "keywords": [0, 0]}
    for name in names:
        sc = load(name)
        kw = keywords_for(packs.network(sc)[1])
        # Only clips whose scripted words name the street: a caller who withholds the address cannot be heard saying it.
        clips = [e for e in sc["events"] if e.get("audio") and (config.ROOT / e["audio"]).exists()
                 and e.get("language", "en") in TRANSCRIBE_LANGS and e.get("truth", {}).get("street")
                 and (norm(e["truth"]["street"]) in norm(e["text"]) or e["id"] in SAYS_STREET)]
        jobs = [(e, with_kw) for e in clips for with_kw in (False, True)]

        def run(job):
            e, with_kw = job
            res = client.transcribe(config.ROOT / e["audio"], BIAS.get(e.get("language", "en")), kw if with_kw else None)
            return (res or {}).get("transcript")

        with ThreadPoolExecutor(WORKERS) as pool:
            texts = list(pool.map(run, jobs))
        rows, score = [], {"plain": [0, 0], "keywords": [0, 0]}
        for (e, with_kw), text in zip(jobs, texts):
            if text is None:
                continue
            street = e["truth"]["street"]
            hit = norm(street) in norm(text)
            key = "keywords" if with_kw else "plain"
            score[key][0] += hit
            score[key][1] += 1
            rows.append({"id": e["id"], "language": e.get("language", "en"), "street": street, "keywords": with_kw,
                         "hit": hit, "transcript": text})
        if not rows:
            print(f"{name}: no live transcripts (is the API allowed for this run?)")
            continue
        for key in score:
            grand[key][0] += score[key][0]
            grand[key][1] += score[key][1]
        print(f"\n== {name}: {len(clips)} clips where the caller names the street")
        for key, (a, n) in score.items():
            print(f"  {key:<9} street heard right in {a}/{n}")
        by_id: dict[str, dict] = {}
        for r in rows:
            by_id.setdefault(r["id"], {})[r["keywords"]] = r
        for cid, pair in by_id.items():
            if False in pair and True in pair and pair[False]["transcript"] != pair[True]["transcript"]:
                print(f"  {cid} [{pair[False]['street']}]\n     plain:    {pair[False]['transcript']}\n     keywords: {pair[True]['transcript']}")
        (out_dir / f"keywords-{name}.json").write_text(json.dumps({"scenario": name, "score": score, "rows": rows},
                                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    if grand["plain"][1]:
        print(f"\nAll: plain {grand['plain'][0]}/{grand['plain'][1]}, keywords {grand['keywords'][0]}/{grand['keywords'][1]}")


if __name__ == "__main__":
    main()
