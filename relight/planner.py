"""Priority scoring and crew dispatch, both in plain code so every number is explainable.

Also simulates the baseline a control room without Relight would follow: handle
faults in the order the first call arrived, and send a troubleshooter to patrol
each one before the right crew can be called, because nobody knows what broke.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .grid import haversine_m

SPEED_KMH = 25
ROAD_FACTOR = 1.3
PATROL_MIN = 40  # baseline: time for a troubleshooter to find and diagnose an unknown fault
NARROW_PATROL_MIN = 15  # Relight: patrol a located device zone when the damage type is still unknown

# Sequential work steps per fault type: (skills needed, minutes on site, label)
STEPS: dict[str, list[tuple[set[str], int, str]]] = {
    "live_wire": [(set(), 15, "make safe and cordon off"), ({"line"}, 75, "repair conductor")],
    "pole_down": [({"line", "bucket_truck"}, 240, "replace pole and restring")],
    "wire_down": [({"line"}, 90, "repair conductor")],
    "tree_on_line": [({"vegetation"}, 60, "clear tree"), ({"line"}, 90, "repair spans")],
    "blown_fuse": [({"troubleshooter"}, 20, "replace fuse")],
    "service_wire": [({"line"}, 45, "repair service wire")],
    "unknown": [({"troubleshooter"}, NARROW_PATROL_MIN, "patrol located zone")],
}
SAFETY = {"live_wire": 1000, "wire_down": 200, "pole_down": 150, "tree_on_line": 100}
AGE_PER_MIN = 2  # older faults climb, so a small one never waits forever
CRITICAL = {"hospital": 400, "water": 300, "shelter": 150}


@dataclass
class Crew:
    id: str
    name: str
    skills: set[str]
    lat: float
    lon: float


@dataclass
class Job:
    fault_id: str
    title: str
    kind: str
    lat: float
    lon: float
    customers_out: int
    confidence: float
    critical: list[str]
    first_report_t: float
    hazard_live: bool = False
    priority: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)


def score(job: Job, now_s: float | None = None) -> None:
    b = {}
    if job.kind in SAFETY:
        b["safety"] = SAFETY[job.kind] if job.kind != "live_wire" or job.hazard_live else 200
    for c in job.critical:
        kind = c.rsplit("(", 1)[-1].rstrip(")")
        b[f"critical: {kind}"] = CRITICAL.get(kind, 100)
    b["customers out"] = round(job.customers_out * job.confidence, 1)
    total_min = sum(m for _, m, _ in STEPS.get(job.kind, STEPS["unknown"]))
    b["quick restore"] = round(job.customers_out * 20 / total_min, 1)
    if now_s is not None:
        b["waiting"] = round(AGE_PER_MIN * max(now_s - job.first_report_t, 0) / 60, 1)
    job.breakdown = b
    job.priority = round(sum(b.values()), 1)


def _travel_min(a: tuple[float, float], b: tuple[float, float]) -> float:
    return haversine_m(a, b) * ROAD_FACTOR / 1000 / SPEED_KMH * 60


def schedule(jobs: list[Job], crews: list[Crew], baseline: bool = False) -> dict:
    """Assign crews step by step. Returns per-job assignments and summary metrics (minutes from now)."""
    free_at = {c.id: 0.0 for c in crews}
    pos = {c.id: (c.lat, c.lon) for c in crews}
    order = sorted(jobs, key=lambda j: j.first_report_t) if baseline else sorted(jobs, key=lambda j: -j.priority)
    plan, cust_min, hazard_wait = [], 0.0, None
    for job in order:
        steps = list(STEPS.get(job.kind, STEPS["unknown"]))
        if baseline:
            # Without located evidence, someone must first find the fault.
            steps = [({"troubleshooter"}, PATROL_MIN, "patrol to find fault")] + [
                s for s in steps if s[2] != "make safe and cordon off"]
        ready, assigned = 0.0, []
        for skills, minutes, label in steps:
            options = [c for c in crews if skills <= c.skills]
            best = min(options, key=lambda c: max(free_at[c.id], ready) + _travel_min(pos[c.id], (job.lat, job.lon)))
            travel = _travel_min(pos[best.id], (job.lat, job.lon))
            start = max(free_at[best.id], ready) + travel
            end = start + minutes
            free_at[best.id], pos[best.id], ready = end, (job.lat, job.lon), end
            assigned.append({"crew": best.id, "crew_name": best.name, "task": label,
                             "travel_min": round(travel), "start_min": round(start), "end_min": round(end)})
            if job.kind == "live_wire" and hazard_wait is None:
                hazard_wait = start if not baseline or label != "patrol to find fault" else end
        cust_min += job.customers_out * ready
        plan.append({"fault_id": job.fault_id, "steps": assigned, "restore_min": round(ready)})
    return {"plan": plan, "customer_minutes": round(cust_min), "hazard_wait_min": round(hazard_wait or 0)}
