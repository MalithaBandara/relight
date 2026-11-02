"""Evidence ablation: measures how well the tracer finds faults when each evidence source is removed.

Evaluates:
- All evidence (baseline)
- Without silence from neighbours
- Without SCADA lockout telemetry
- Without neighbour probe questions
- Without damage photos
- Without smart meters (for scenarios with AMI)
- Calls only
- SCADA only

Outputs data/analysis_ablation.json for GET /api/analysis/ablation and the Analysis dialog.
Usage: python scripts/ablate.py
"""

from __future__ import annotations

import asyncio
import heapq
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import config
from relight.engine import Engine
from relight.network import live_transformers
from relight.scenario import MAX_CLOCK_S, Replayer, load

STEP_S = 30


async def run_scenario(name: str, ablate: set[str]) -> dict:
    sc = load(name)

    async def quiet(_m):
        pass

    engine = Engine(sc, quiet)
    engine.ablate = set(ablate)
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
        for inc in engine.incidents:
            for p in inc["plans"]:
                if p["safe"] and p["customers"] and not inc["switching"] and inc["status"] != "restored":
                    await engine.apply_plan(inc["id"], p["id"])

    truth = engine.score_against_truth()
    found = sum(1 for tf in truth if tf["found"])
    total = len(truth)
    loc_times = [tf["located_at"] / 60 for tf in truth if tf.get("located_at") is not None]
    loc_median = round(statistics.median(loc_times), 1) if loc_times else None
    conf_mean = round(statistics.mean([inc["confidence"] for inc in engine.incidents]), 2) if engine.incidents else 0.0

    live = live_transformers(engine.feeder, engine.belief())
    dead = set(engine.feeder.transformers) - live
    dark_at_end = sum(engine.customers.get(t, 0) for t in dead) + sum(len(i["dead_customers"]) for i in engine._active())

    return {
        "found": found,
        "total": total,
        "located_min_median": loc_median,
        "confidence_mean": conf_mean,
        "dark_at_end": dark_at_end,
    }


def main():
    scenarios = ["galle_storm", "houston_hurricane"]
    runs = []

    for sc_name in scenarios:
        sc = load(sc_name)
        title = sc["title"]
        print(f"\nRunning ablation on {title} ({sc_name})...")

        tests = [
            ("All evidence", set(), True),
            ("Without silence", {"silence"}, False),
            ("Without SCADA", {"scada"}, False),
            ("Without neighbour probes", {"probes"}, False),
            ("Without damage photos", {"damage"}, False),
        ]
        if sc.get("pack", {}).get("smart_meters"):
            tests.append(("Without smart meters", {"meters"}, False))
        tests.append(("Calls only", {"silence", "scada", "probes", "damage", "meters"}, False))
        tests.append(("SCADA only", {"calls", "silence", "probes", "damage", "meters"}, False))

        rows = []
        for label, ablate_set, is_base in tests:
            print(f"  {label}...", end=" ", flush=True)
            res = asyncio.run(run_scenario(sc_name, ablate_set))
            print(f"{res['found']}/{res['total']} found, {res['dark_at_end']} dark")
            rows.append({
                "label": label,
                "baseline": is_base,
                "found": res["found"],
                "total": res["total"],
                "located_min_median": res["located_min_median"],
                "confidence_mean": res["confidence_mean"],
                "dark_at_end": res["dark_at_end"],
            })

        runs.append({
            "scenario": sc_name,
            "title": title,
            "rows": rows,
        })

    out_data = {
        "runs": runs,
        "note": "Replayed in mock mode with each evidence source removed. Tested on synthetic storm events.",
    }

    out_file = config.DATA_DIR / "analysis_ablation.json"
    out_file.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote ablation analysis to {out_file}")


if __name__ == "__main__":
    main()
