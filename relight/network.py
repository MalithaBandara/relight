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
            link(("bus", s.section), ("bus", feeder.feeder2_bus), [s.id])
    feeder.__dict__["_graph"] = adj
    return adj


def live_sections(feeder: Feeder, st: NetworkState, ignore_faults: bool = False) -> set[str]:
    """Sections whose body is energised. With ignore_faults, faulted bodies conduct (used to ask
    'would this switching energise the fault?')."""
    adj = _graph(feeder)
    blocked = set() if ignore_faults else st.faulted
    seen = {("bus", feeder.root)} | ({("bus", feeder.feeder2_bus)} if feeder.feeder2_bus else set())
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


def check_plan(feeder: Feeder, belief: NetworkState, plan: Plan, work_zones: dict[str, str],
               customers: dict[str, int]) -> Plan:
    """Simulate a plan step by step. Blocks it at the first step that would energise a believed
    fault or a crew's work zone; otherwise reports which transformers it restores."""
    st = belief.copy()
    before = live_transformers(feeder, belief)
    already = live_sections(feeder, belief, ignore_faults=True)  # only what the plan newly energises counts
    for i, (op, dev) in enumerate(plan.steps, 1):
        (st.open.discard if op == "close" else st.open.add)(dev)
        reach = live_sections(feeder, st, ignore_faults=True) - already
        hot_fault = sorted(reach & belief.faulted)
        hot_zone = sorted(s for s in reach if s in work_zones)
        hot_suspect = sorted(reach & belief.suspect)
        if hot_zone:
            s = hot_zone[0]
            plan.safe = False
            plan.reason = (f"Step {i} ({op} {dev}) would energise section {s} on {feeder.sections[s].street} "
                           f"where {work_zones[s]} is working")
            return plan
        if hot_fault:
            s = hot_fault[0]
            plan.safe = False
            plan.reason = (f"Step {i} ({op} {dev}) would re-energise the faulted section {s} on "
                           f"{feeder.sections[s].street}: it would trip again or back-feed the fault")
            return plan
        if hot_suspect:
            s = hot_suspect[0]
            plan.safe = False
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
    switches = {s.section: s.id for s in feeder.switches.values() if s.kind == "switch"}
    ties = [s for s in feeder.switches.values() if s.kind == "tie" and s.id in belief.open]
    plans: list[Plan] = []
    if device and device in belief.open and feeder.devices[device].kind in REMOTE_KINDS:
        plans.append(Plan("reclose", f"Reclose {device}", [("close", device)]))
    for t in ties:
        plans.append(Plan(f"tie-{t.id}", f"Close tie {t.id} to Feeder 2", [("close", t.id)]))

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
        steps = [("open", s) for s in ([upstream] if upstream else []) + downstream]
        if device and device in belief.open and feeder.devices[device].kind in REMOTE_KINDS:
            steps.append(("close", device))
        steps += [("close", t.id) for t in ties]
        names = " and ".join(s for _, s in steps if _ == "open")
        plans.append(Plan("isolate", f"Isolate with {names}, then restore around the fault", steps))
    return [check_plan(feeder, belief, p, work_zones, customers) for p in plans]
