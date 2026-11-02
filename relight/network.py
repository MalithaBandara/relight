"""Power flow and switching: which transformers are live, and is a switching plan safe?

The network is walked as a graph of buses and section bodies. A section's body (its
line and transformers) is joined to its upstream bus through whatever devices sit at
its head (recloser, fuse, sectionalising switch), and to its downstream bus directly.
A faulted section body carries no power. Feeder 2 reaches the far end of Temple Road
through the normally-open tie switch TS-1, so power can flow "backwards" up a section
once it is closed.

The same model serves two purposes: the physical truth of the simulated storm, and
Relight's belief about the network (its located faults plus the device states it
knows). Restoration plans are checked against the belief: a plan is blocked if any
step would energise a section believed faulted or a section where a crew is working.

NOTE: There is no load-flow check (voltage, current, thermal capacity), so a plan using
multiple ties may overload a feeder in reality.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .grid import Feeder

REMOTE_KINDS = {"breaker", "recloser", "switch", "tie"}


@dataclass
class NetworkState:
    open: set[str] = field(default_factory=set)  # open devices and switches (ties start open)
    faulted: set[str] = field(default_factory=set)  # section bodies that are broken / dead
    dead_transformers: set[str] = field(default_factory=set)  # blown transformer fuses
    dead_customers: set[str] = field(default_factory=set)  # accounts behind a broken service wire
    suspect: set[str] = field(default_factory=set)  # sections where a fault is known but not yet pinned down

    def copy(self) -> "NetworkState":
        return NetworkState(set(self.open), set(self.faulted), set(self.dead_transformers), set(self.dead_customers),
                            set(self.suspect))


def _heads(feeder: Feeder) -> dict[str, list[str]]:
    """Section id -> ids of devices and switches at its head."""
    heads: dict[str, list[str]] = {}
    for d in feeder.devices.values():
        if d.kind != "xfmr_fuse":
            heads.setdefault(d.section, []).append(d.id)
    for s in feeder.switches.values():
        if s.kind == "switch":
            heads.setdefault(s.section, []).append(s.id)
    return heads


def _graph(feeder: Feeder) -> dict[tuple[str, str], list[tuple[tuple[str, str], tuple[str, ...]]]]:
    """Bus/section adjacency, built once per feeder: node -> [(neighbour, devices that must be closed)]."""
    if "_graph" in feeder.__dict__:
        return feeder.__dict__["_graph"]
    heads = _heads(feeder)
    adj: dict = {}

    def link(a, b, devs=()):
        adj.setdefault(a, []).append((b, tuple(devs)))
        adj.setdefault(b, []).append((a, tuple(devs)))

    for sid, sec in feeder.sections.items():
        link(("bus", sec.from_bus), ("sec", sid), heads.get(sid, []))
        link(("sec", sid), ("bus", sec.to_bus))
    for s in feeder.switches.values():
        if s.kind == "tie":
            target = getattr(s, "target_bus", None) or feeder.feeder2_bus
            if target:
                link(("bus", s.section), ("bus", target), [s.id])
    feeder.__dict__["_graph"] = adj
    return adj


def live_sections(feeder: Feeder, st: NetworkState, ignore_faults: bool = False) -> set[str]:
    """Sections whose body is energised. With ignore_faults, faulted bodies conduct (used to ask
    'would this switching energise the fault?')."""
    # NOTE: There is no load-flow check (voltage, current, thermal capacity), so a plan using
    # one or more ties may overload a neighbouring feeder in reality.
    adj = _graph(feeder)
    blocked = set() if ignore_faults else st.faulted
    sources = {("bus", feeder.root)}
    if getattr(feeder, "feeder2_bus", None):
        sources.add(("bus", feeder.feeder2_bus))
    for b in getattr(feeder, "source_buses", set()):
        sources.add(("bus", b))
    seen = set(sources)
    stack = list(seen)
    while stack:
        node = stack.pop()
        for nxt, devs in adj.get(node, ()):
            if nxt in seen or (devs and not st.open.isdisjoint(devs)):
                continue
            if nxt[0] == "sec" and nxt[1] in blocked:
                continue
            seen.add(nxt)
            stack.append(nxt)
    return {n[1] for n in seen if n[0] == "sec"}


def live_transformers(feeder: Feeder, st: NetworkState) -> set[str]:
    live = live_sections(feeder, st)
    return {t for s in live for t in feeder.transformers_on(s) if t not in st.dead_transformers}


@dataclass
class Plan:
    id: str
    title: str
    steps: list[tuple[str, str]]  # (op "open"/"close", device id)
    safe: bool = True
    reason: str = ""
    restores: list[str] = field(default_factory=list)  # transformers that come back on
    customers: int = 0
    ties: list[str] = field(default_factory=list)
    recommended: bool = False
    partial: bool = False
    blocked_by: str | None = None
    ops: int = 0


def check_plan(feeder: Feeder, belief: NetworkState, plan: Plan, work_zones: dict[str, str],
               customers: dict[str, int]) -> Plan:
    """Simulate a plan step by step. Blocks it at the first step that would energise a believed
    fault or a crew's work zone; otherwise reports which transformers it restores."""
    st = belief.copy()
    before = live_transformers(feeder, belief)
    already = live_sections(feeder, belief, ignore_faults=True)  # only what the plan newly energises counts
    plan.ops = len(plan.steps)
    plan.ties = [dev for op, dev in plan.steps if dev in feeder.switches and feeder.switches[dev].kind == "tie"]
    for i, (op, dev) in enumerate(plan.steps, 1):
        (st.open.discard if op == "close" else st.open.add)(dev)
        reach = live_sections(feeder, st, ignore_faults=True) - already
        hot_fault = sorted(reach & belief.faulted)
        hot_zone = sorted(s for s in reach if s in work_zones)
        hot_suspect = sorted(reach & belief.suspect)
        if hot_zone:
            s = hot_zone[0]
            plan.safe = False
            plan.blocked_by = f"crew {work_zones[s]} working on {feeder.sections[s].street}"
            plan.reason = (f"Step {i} ({op} {dev}) would energise section {s} on {feeder.sections[s].street} "
                           f"where {work_zones[s]} is working")
            return plan
        if hot_fault:
            s = hot_fault[0]
            plan.safe = False
            plan.blocked_by = "would re-energise the faulted section"
            plan.reason = (f"Step {i} ({op} {dev}) would re-energise the faulted section {s} on "
                           f"{feeder.sections[s].street}: it would trip again or back-feed the fault")
            return plan
        if hot_suspect:
            s = hot_suspect[0]
            plan.safe = False
            plan.blocked_by = "unconfirmed fault in zone"
            plan.reason = (f"Step {i} ({op} {dev}) would energise section {s} on {feeder.sections[s].street}, "
                           f"inside a fault zone whose exact location is not confirmed yet")
            return plan
    after = live_transformers(feeder, st)
    plan.restores = sorted(after - before)
    plan.customers = sum(customers.get(t, 0) for t in plan.restores)
    plan.reason = f"Isolates the fault first; restores {plan.customers} customers" if plan.customers else \
        "Safe, but restores nobody"
    return plan


def restoration_plans(feeder: Feeder, belief: NetworkState, faulted_section: str, device: str | None,
                      work_zones: dict[str, str], customers: dict[str, int]) -> list[Plan]:
    """Switching options for one located fault: the tempting shortcuts and the isolate-then-restore plan."""
    # NOTE: There is no load-flow check (voltage, current, thermal capacity), so a plan using
    # one or more ties may overload a neighbouring feeder in reality.
    switches = {s.section: s.id for s in feeder.switches.values() if s.kind == "switch"}
    ties = [s for s in feeder.switches.values() if s.kind == "tie" and s.id in belief.open]
    plans: list[Plan] = []
    if device and device in belief.open and feeder.devices[device].kind in REMOTE_KINDS:
        plans.append(Plan("reclose", f"Reclose {device}", [("close", device)]))
    for t in ties:
        target_name = getattr(t, "target_bus", None) or feeder.feeder2_label or "Feeder 2"
        plans.append(Plan(f"tie-{t.id}", f"Close tie {t.id} to {target_name}" if len(ties) == 1 else f"Close tie {t.id}", [("close", t.id)]))
    if len(ties) > 1:
        plans.append(Plan("tie-all", f"Close all ties ({', '.join(t.id for t in ties)})", [("close", t.id) for t in ties]))

    # Isolation: the nearest switch at or above the fault (below the tripped device) and the
    # nearest switch on every branch leaving the faulted section.
    upstream = None
    sid: str | None = faulted_section
    stop = feeder.devices[device].section if device else None
    while sid:
        if sid in switches:
            upstream = switches[sid]
            break
        if sid == stop:
            break
        sid = feeder.parent_section.get(feeder.sections[sid].from_bus)
    downstream: list[str] = []
    for child in feeder.children.get(feeder.sections[faulted_section].to_bus, []):
        stack = [child]
        while stack:
            c = stack.pop()
            if c in switches:
                downstream.append(switches[c])
                continue
            stack.extend(feeder.children.get(feeder.sections[c].to_bus, []))
    if upstream or downstream:
        open_steps = [("open", s) for s in ([upstream] if upstream else []) + downstream]
        dev_steps = [("close", device)] if (device and device in belief.open and feeder.devices[device].kind in REMOTE_KINDS) else []
        names = " and ".join(s for _, s in open_steps)
        if len(ties) <= 1:
            steps = open_steps + dev_steps + [("close", t.id) for t in ties]
            plans.append(Plan("isolate", f"Isolate with {names}, then restore around the fault", steps))
        else:
            for t in ties:
                steps_t = open_steps + dev_steps + [("close", t.id)]
                plans.append(Plan(f"isolate-{t.id}", f"Isolate with {names}, then restore via tie {t.id}", steps_t))
            steps_all = open_steps + dev_steps + [("close", t.id) for t in ties]
            plans.append(Plan("isolate-all", f"Isolate with {names}, then restore via all ties ({', '.join(t.id for t in ties)})", steps_all))
    checked = [check_plan(feeder, belief, p, work_zones, customers) for p in plans]
    safe_plans = [p for p in checked if p.safe and p.customers > 0]
    if safe_plans:
        max_cust = max(p.customers for p in safe_plans)
        for p in safe_plans:
            if p.customers < max_cust:
                p.partial = True
        best = max(safe_plans, key=lambda p: (p.customers, -p.ops))
        best.recommended = True
    return checked
