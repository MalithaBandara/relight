"""What-if sensitivity analysis: sweeps crew counts, call reporting rates and patrol times.

Computes the range of customer-minutes saved against the first-call-first-served baseline.
Outputs data/analysis_sensitivity.json for GET /api/analysis/sensitivity and the Analysis dialog.
Usage: python scripts/sensitivity.py
"""

from __future__ import annotations

import asyncio
import copy
import heapq
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import config
from relight import planner
from relight.engine import Engine
from relight.planner import Crew, Job, STEPS, schedule, score
from relight.scenario import MAX_CLOCK_S, Replayer, load

STEP_S = 30


async def get_incident_jobs(name: str) -> tuple[dict, list[Job], list[Crew]]:
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
        for inc in engine.incidents:
            for p in inc["plans"]:
                if p["safe"] and p["customers"] and not inc["switching"] and inc["status"] != "restored":
                    await engine.apply_plan(inc["id"], p["id"])

    # Build final jobs as in engine._score_and_plan
    jobs = []
    live_wire_safe = any(h["safe"] for h in engine.hazards if h["kind"] == "live_wire")
    for inc in engine.incidents:
        j = Job(inc["id"], inc["title"], inc["kind"], inc["lat"], inc["lon"], inc["customers_out"],
                inc["confidence"], inc["critical"], inc["first_t"],
                inc["kind"] == "live_wire" and not live_wire_safe,
                backup_failed=sum(1 for b in engine.backup_failed.values()
                                  if inc["status"] != "restored" and (b["xf"] in inc["out"] or b["account"] in inc["dead_customers"])))
        score(j, engine.elapsed)
        jobs.append(j)

    crews = [Crew(c["id"], c["name"], set(c["skills"]), *engine.feeder.bus_pos[c["base"]])
             for c in engine.crews.values()]
    return sc, jobs, crews


def sweep_scenario(sc: dict, base_jobs: list[Job], base_crews: list[Crew]) -> dict:
    sc_name = sc["id"]
    title = sc["title"]

    # Base schedule to check dispatch order
    r_base = schedule(base_jobs, base_crews, baseline=False)
    dispatched_order = []
    for p in r_base["plan"]:
        for s in p["steps"]:
            if s["crew"] not in dispatched_order:
                dispatched_order.append(s["crew"])

    required_skills = set()
    for j in base_jobs:
        for skills, _, _ in STEPS.get(j.kind, STEPS["unknown"]):
            if skills:
                required_skills.add(frozenset(skills))

    # Droppable line crew: pick first dispatched line crew whose removal preserves feasibility
    line_crews = [c for c in base_crews if "line" in c.skills]
    droppable_line_crews = [
        c for c in line_crews
        if all(any(req <= other.skills for other in base_crews if other.id != c.id) for req in required_skills)
    ]
    target_line_crew = None
    for cid in dispatched_order:
        c = next((x for x in droppable_line_crews if x.id == cid), None)
        if c:
            target_line_crew = c
            break
    if not target_line_crew and droppable_line_crews:
        target_line_crew = droppable_line_crews[0]

    # Droppable troubleshooter: pick first dispatched troubleshooter whose removal preserves feasibility
    ts_crews = [c for c in base_crews if "troubleshooter" in c.skills]
    droppable_ts_crews = [
        c for c in ts_crews
        if all(any(req <= other.skills for other in base_crews if other.id != c.id) for req in required_skills)
    ]
    target_ts_crew = None
    for cid in dispatched_order:
        c = next((x for x in droppable_ts_crews if x.id == cid), None)
        if c:
            target_ts_crew = c
            break
    if not target_ts_crew and droppable_ts_crews:
        target_ts_crew = droppable_ts_crews[0]

    # Symmetric call delay variations:
    # 1. Late line-fault reports (+15 min, all but fuse and service-wire jobs)
    jobs_late_line = []
    for j in base_jobs:
        cj = copy.deepcopy(j)
        if cj.kind not in ("blown_fuse", "service_wire"):
            cj.first_report_t += 900
        jobs_late_line.append(cj)

    # 2. Late branch reports (+15 min fuse, +30 min service wire)
    jobs_late_branch = []
    for j in base_jobs:
        cj = copy.deepcopy(j)
        if cj.kind == "blown_fuse":
            cj.first_report_t += 900
        elif cj.kind == "service_wire":
            cj.first_report_t += 1800
        jobs_late_branch.append(cj)

    settings_configs = [
        ("Base (standard crews, normal calls)", base_crews, base_jobs, 40),
    ]

    if target_line_crew:
        crews_minus_line = [c for c in base_crews if c.id != target_line_crew.id]
        settings_configs.append((f"Fewer crews (-1 line crew {target_line_crew.id})", crews_minus_line, base_jobs, 40))
    else:
        print(f"Skipping line crew removal for {sc_name}: no droppable line crew available")

    if target_ts_crew:
        crews_minus_ts = [c for c in base_crews if c.id != target_ts_crew.id]
        settings_configs.append((f"Fewer crews (-1 troubleshooter {target_ts_crew.id})", crews_minus_ts, base_jobs, 40))
    else:
        print(f"Skipping troubleshooter removal for {sc_name}: no droppable troubleshooter available")

    crews_plus_line = base_crews + [Crew("C-EXTRA1", "Line Crew Extra", {"line", "bucket_truck"}, base_crews[0].lat, base_crews[0].lon)]
    crews_plus_t = base_crews + [Crew("C-EXTRA2", "Troubleshooter Extra", {"troubleshooter"}, base_crews[0].lat, base_crews[0].lon)]

    settings_configs.extend([
        ("Extra crew (+1 line crew)", crews_plus_line, base_jobs, 40),
        ("Extra crew (+1 troubleshooter)", crews_plus_t, base_jobs, 40),
        ("Late line-fault reports (+15 min, all but fuse and service-wire jobs)", base_crews, jobs_late_line, 40),
        ("Late branch reports (+15 min fuse, +30 min service wire)", base_crews, jobs_late_branch, 40),
        ("Fast baseline patrol (30 min)", base_crews, base_jobs, 30),
        ("Slow baseline patrol (50 min)", base_crews, base_jobs, 50),
    ])

    settings = []
    savings = []

    orig_patrol = planner.PATROL_MIN
    try:
        for label, crews_subset, jobs_subset, patrol_min in settings_configs:
            planner.PATROL_MIN = patrol_min
            jobs = [copy.deepcopy(j) for j in jobs_subset]
            crews = [copy.deepcopy(c) for c in crews_subset]
            r_res = schedule(jobs, crews, baseline=False)
            b_res = schedule(jobs, crews, baseline=True)
            relight_cmi = r_res["customer_minutes"]
            base_cmi = b_res["customer_minutes"]
            pct = round(100 * (base_cmi - relight_cmi) / max(base_cmi, 1), 1)
            savings.append(pct)
            settings.append({
                "label": label,
                "relight": relight_cmi,
                "baseline": base_cmi,
            })
    finally:
        planner.PATROL_MIN = orig_patrol

    return {
        "scenario": sc_name,
        "title": title,
        "baseline_label": "first-call-first-served",
        "saving_pct": {
            "min": round(min(savings)),
            "median": round(statistics.median(savings)),
            "max": round(max(savings)),
        },
        "settings": settings,
    }


def main():
    scenarios = ["galle_storm", "houston_hurricane"]
    runs = []

    for name in scenarios:
        print(f"Evaluating sensitivity on {name}...")
        sc, jobs, crews = asyncio.run(get_incident_jobs(name))
        res = sweep_scenario(sc, jobs, crews)
        print(f"  Saving range: {res['saving_pct']['min']}% to {res['saving_pct']['max']}% (median {res['saving_pct']['median']}%) across {len(res['settings'])} settings")
        runs.append(res)

    out_data = {
        "runs": runs,
        "note": "Sweep covers crew availability (removing first dispatched line crew/troubleshooter, adding extra crews), reporting order variations, and manual patrol speed (30–50 min). Late-report variations affect the first-call baseline's ordering only, as Relight prioritizes faults by evidence and customer count.",
    }

    out_file = config.DATA_DIR / "analysis_sensitivity.json"
    out_file.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote sensitivity analysis to {out_file}")


if __name__ == "__main__":
    main()
