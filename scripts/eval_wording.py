"""Evaluate Muse Spark agent wording quality across languages and scenarios.

Counts:
- Total Spark-worded lines per language
- Lines kept by the deterministic fact check
- Lines rejected and the specific reasons (number, street, time, id)
- Median latency (wait time) from the response cache

Outputs data/analysis_wording.json for GET /api/analysis/wording and the Analysis dialog.
Usage: python scripts/eval_wording.py
"""

from __future__ import annotations

import asyncio
import heapq
import json
from pathlib import Path
import re
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import config
from relight.engine import Engine
from relight.scenario import MAX_CLOCK_S, Replayer, load

STEP_S = 30


def classify_reason(dropped_item: str) -> str:
    item = str(dropped_item).strip()
    if re.match(r"^\d{1,2}:\d{2}$", item):
        return "time"
    if re.match(r"^\d+$", item):
        return "number"
    if re.match(r"^(?:I\d+|T-\d+|SW-\d+|FUS-\d+|XF-\d+)$", item, re.I):
        return "id"
    return "street"


def get_spark_content_latencies() -> dict[str, float]:
    content_to_lat = {}
    for p in Path(config.ROOT / ".cache" / "model").glob("spark-*.json"):
        try:
            d = json.loads(p.read_text("utf-8"))
            if "_latency_s" in d:
                c = d.get("choices", [{}])[0].get("message", {}).get("content", "")
                if c:
                    content_to_lat[c.strip()] = float(d["_latency_s"])
        except Exception:
            pass
    return content_to_lat


async def eval_scenario(name: str, content_to_lat: dict[str, float]) -> dict:
    sc = load(name)

    async def quiet(_m):
        pass

    engine = Engine(sc, quiet)
    replayer = Replayer(sc, engine.handle)
    engine.sim = replayer

    clock = 0.0
    while clock < MAX_CLOCK_S:
        if replayer.queue and replayer.queue[0][0] <= clock:
            _, _, e = heapq.heappop(replayer.queue)
            await replayer.deliver(e)
            continue
        if not replayer.queue and clock >= sc["duration_s"] and not engine.busy():
            break
        clock += STEP_S
        await engine.advance(clock)

    # Collect agent turns
    by_lang: dict[str, dict] = {}
    lats_by_lang: dict[str, list[float]] = {}

    calls = [m["call"] for m in engine.messages if "call" in m]
    for c in calls:
        lang = c.get("language", "en")
        if lang not in by_lang:
            by_lang[lang] = {
                "lang": lang,
                "lines": 0,
                "kept": 0,
                "rejected": 0,
                "reasons": {},
                "median_wait_s": None,
            }

        for turn in c.get("turns", []):
            if turn.get("who") != "agent":
                continue
            model = turn.get("model", "")
            is_spark = model == "Muse Spark" or "rejected" in turn or "failed fact check" in model
            if not is_spark:
                continue

            by_lang[lang]["lines"] += 1
            txt = turn.get("text", "").strip()
            if txt in content_to_lat:
                lats_by_lang.setdefault(lang, []).append(content_to_lat[txt])

            if "rejected" in turn or "failed fact check" in model:
                by_lang[lang]["rejected"] += 1
                for item in turn.get("rejected", ["fact"]):
                    r_type = classify_reason(item)
                    by_lang[lang]["reasons"][r_type] = by_lang[lang]["reasons"].get(r_type, 0) + 1
            else:
                by_lang[lang]["kept"] += 1

    for lang, info in by_lang.items():
        lats = lats_by_lang.get(lang, [])
        info["median_wait_s"] = round(statistics.median(lats), 1) if lats else None

    # Filter languages with lines, or populate defaults
    lang_list = list(by_lang.values())
    if not lang_list:
        # Fallback if no voiced calls occurred
        lang_list = [{
            "lang": "en",
            "lines": 0,
            "kept": 0,
            "rejected": 0,
            "reasons": {},
            "median_wait_s": None,
        }]

    return {
        "scenario": name,
        "title": sc["title"],
        "languages": lang_list,
    }


def main():
    content_to_lat = get_spark_content_latencies()

    scenarios = ["galle_storm", "houston_hurricane", "chennai_cyclone"]
    runs = []

    for name in scenarios:
        print(f"Evaluating wording for {name}...")
        res = asyncio.run(eval_scenario(name, content_to_lat))
        for l in res["languages"]:
            pct = round(100 * l["kept"] / max(l["lines"], 1))
            print(f"  {l['lang']}: {l['kept']}/{l['lines']} kept ({pct}%), {l['rejected']} rejected, median wait {l['median_wait_s']}s")
        runs.append(res)

    out_data = {
        "runs": runs,
        "note": "Muse Spark rewordings verified by deterministic fact-check code. Latency median measured per language from cached API responses.",
    }

    out_file = config.DATA_DIR / "analysis_wording.json"
    out_file.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote wording analysis to {out_file}")


if __name__ == "__main__":
    main()
