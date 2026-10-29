"""Fault tracer: which devices opened (or which lines broke) best explain the evidence?

Deterministic and explainable. Each candidate is a protective device or an
unprotected line break. A hypothesis is a set of candidates; its score is a
log-likelihood over:

- complaints per service transformer (customers out call with probability q,
  customers with power complain only rarely, at rate EPS),
- silence: an outage that covers many transformers nobody has called from is
  less likely (neighbours' behaviour is correlated, so silence counts per group of
  HOUSEHOLDS_PER_SIGNAL customers, not per customer),
- answers to questions the agent sent to customers ("is your power on?"),
- SCADA: a monitored device that locked out must be explained, and a monitored
  device cannot have opened silently,
- located physical damage (hazard reports, photos, crew notes) inside a
  candidate's protection zone.

A greedy search adds the candidate that most improves the score until nothing
helps. Each chosen fault's confidence is its share of probability against the
alternatives that could replace it (an upstream fuse instead of a transformer
fuse, and so on). The most useful alternative becomes the agent's next question.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .grid import Feeder, haversine_m

EPS = 0.003  # chance a customer with power reports an outage anyway
HOUSEHOLDS_PER_SIGNAL = 5
ACCEPT_NATS = 1.0
PRIORS = {"breaker": 0.004, "recloser": 0.02, "fuse": 0.02, "xfmr_fuse": 0.012, "line": 0.003}
DAMAGE_COMPAT = {
    "pole_down": {"breaker", "recloser", "fuse", "line"},
    "tree_on_line": {"breaker", "recloser", "fuse", "line"},
    "wire_down": {"breaker", "recloser", "fuse", "line"},
    "live_wire": {"line", "recloser", "fuse"},
    "blown_fuse": {"xfmr_fuse", "fuse"},
    "transformer_bang": {"xfmr_fuse"},
    "transformer_failure": {"xfmr_fuse"},
}


def call_probability(elapsed_s: float) -> float:
    """Chance an affected customer has called by now; rises over the first ~15 minutes."""
    return 0.004 + 0.12 * (1 - math.exp(-elapsed_s / 420))


@dataclass
class Damage:
    source: str  # evidence id (complaint, photo, crew note)
    kind: str
    section: str
    transformer: str | None
    strength: float  # nats
    lat: float
    lon: float


@dataclass
class Evidence:
    reports: dict[str, set[str]] = field(default_factory=dict)  # transformer -> reporting accounts
    partial: dict[str, set[str]] = field(default_factory=dict)  # transformer -> accounts with partial power
    probes: dict[str, bool] = field(default_factory=dict)  # transformer -> power is on?
    scada_open: set[str] = field(default_factory=set)
    damage: list[Damage] = field(default_factory=list)
    report_ids: dict[str, list[str]] = field(default_factory=dict)  # transformer -> complaint ids


@dataclass
class Candidate:
    id: str
    kind: str
    label: str
    section: str
    out: frozenset[str]
    zone: frozenset[str]
    scada: bool
    lat: float
    lon: float


@dataclass
class Located:
    candidate: Candidate
    confidence: float
    alternative: Candidate | None
    alt_confidence: float
    score_gain: float
    damage: list[Damage]
    reasons: list[str]


class Tracer:
    def __init__(self, feeder: Feeder, customers_per_xfmr: dict[str, int]) -> None:
        self.feeder = feeder
        self.n = customers_per_xfmr
        protected = {d.section for d in feeder.devices.values() if d.kind != "xfmr_fuse"}
        self.candidates: dict[str, Candidate] = {}
        for d in feeder.devices.values():
            if d.kind == "xfmr_fuse":
                zone = frozenset({d.section})
            else:
                zone = frozenset(s for s in self._zone(d.section, protected))
            self.candidates[d.id] = Candidate(d.id, d.kind, d.label, d.section, feeder.downstream[d.id], zone,
                                              d.scada, d.lat, d.lon)
        for sid, sec in feeder.sections.items():
            out = frozenset(t for s in feeder.sections_below(sid) for t in feeder.transformers
                            if feeder.transformers[t].section == s)
            if not out:
                continue
            lat, lon = feeder.point_on_section(sid, sec.length_m / 2)
            cid = f"LINE-{sid}"
            self.candidates[cid] = Candidate(cid, "line", f"Broken conductor on {sec.street} ({sid})", sid, out,
                                             frozenset({sid}), False, lat, lon)

    def _zone(self, section: str, protected: set[str]) -> list[str]:
        """Sections a device protects directly (stop at the next downstream device)."""
        out, stack = [], [section]
        while stack:
            sid = stack.pop()
            out.append(sid)
            for child in self.feeder.children.get(self.feeder.sections[sid].to_bus, []):
                if child not in protected:
                    stack.append(child)
        return out

    # ---- scoring ----------------------------------------------------------

    def _per_transformer(self, ev: Evidence, q: float) -> dict[str, float]:
        """Log-likelihood gain for each transformer of being out vs energised."""
        gain: dict[str, float] = {}
        for t in self.feeder.transformers:
            n = self.n.get(t, 0)
            k = len(ev.reports.get(t, ()))
            silent = max(n - k, 0) / HOUSEHOLDS_PER_SIGNAL
            g = k * math.log(q / EPS) + silent * (math.log(1 - q) - math.log(1 - EPS))
            if t in ev.probes:
                g += math.log(0.03 / 0.97) if ev.probes[t] else math.log(0.97 / 0.03)
            gain[t] = g
        return gain

    def score(self, hyp: list[Candidate], ev: Evidence, gain: dict[str, float]) -> float:
        out = frozenset().union(*(c.out for c in hyp)) if hyp else frozenset()
        s = sum(gain[t] for t in out)
        for c in hyp:
            p = PRIORS[c.kind]
            s += math.log(p / (1 - p))
            # Partial power points to an open conductor, not an operated fuse.
            n_partial = sum(len(ev.partial.get(t, ())) for t in c.out)
            s += n_partial * (math.log(3.0) if c.kind == "line" else math.log(0.5))
        chosen = {c.id for c in hyp}
        for dev in ev.scada_open:
            if dev not in chosen:
                s += math.log(0.005)
        for c in hyp:
            if c.scada and c.id not in ev.scada_open:
                s += math.log(0.02)
        for dmg in ev.damage:
            best = 0.0
            for c in hyp:
                if dmg.section in c.zone and c.kind in DAMAGE_COMPAT.get(dmg.kind, ()):
                    if c.kind == "xfmr_fuse" and dmg.transformer and dmg.transformer != "T-" + c.id[3:]:
                        continue
                    w = dmg.strength * (0.5 if dmg.kind == "live_wire" and c.kind != "line" else 1.0)
                    best = max(best, w)
            s += best
        return s

    def locate(self, ev: Evidence, elapsed_s: float) -> list[Located]:
        q = call_probability(elapsed_s)
        gain = self._per_transformer(ev, q)
        # Only candidates touching some evidence are worth trying.
        touched = set(ev.reports) | {d.section for d in ev.damage}
        pool = [c for c in self.candidates.values()
                if c.out & set(ev.reports) or c.id in ev.scada_open or c.zone & touched]
        hyp: list[Candidate] = []
        base = self.score(hyp, ev, gain)
        # Greedy forward selection, with a backward pass after each addition so a broad
        # early guess (one big upstream device) is dropped once specific faults explain it.
        for _ in range(4 * len(pool)):
            best, best_s = None, base + ACCEPT_NATS
            for c in pool:
                if c in hyp:
                    continue
                s = self.score(hyp + [c], ev, gain)
                if s > best_s:
                    best, best_s = c, s
            if best is None:
                break
            hyp.append(best)
            base = best_s
            pruned = True
            while pruned:
                pruned = False
                for c in list(hyp):
                    s = self.score([h for h in hyp if h is not c], ev, gain)
                    if s >= base:
                        hyp.remove(c)
                        base, pruned = s, True

        located = []
        for c in hyp:
            rest = [h for h in hyp if h is not c]
            alts: list[tuple[float, Candidate | None]] = [(self.score(rest, ev, gain), None)]
            for a in pool:
                if a in hyp or not (a.out & c.out):
                    continue
                alts.append((self.score(rest + [a], ev, gain), a))
            mine = base
            top = max([mine] + [s for s, _ in alts])
            z = math.exp(mine - top) + sum(math.exp(s - top) for s, _ in alts)
            conf = math.exp(mine - top) / z
            alt_s, alt = max(alts, key=lambda x: x[0])
            dmg = [d for d in ev.damage if d.section in c.zone and c.kind in DAMAGE_COMPAT.get(d.kind, ())]
            located.append(Located(c, conf, alt, math.exp(alt_s - top) / z, mine - alt_s, dmg,
                                   self._reasons(c, ev)))
        return located

    def _reasons(self, c: Candidate, ev: Evidence) -> list[str]:
        r = []
        xf = [t for t in c.out if ev.reports.get(t)]
        n_rep = sum(len(ev.reports[t]) for t in xf)
        silent = [t for t in c.out if not ev.reports.get(t)]
        if n_rep:
            r.append(f"{n_rep} customers on {len(xf)} of its {len(c.out)} transformers report no power")
        if c.id in ev.scada_open:
            r.append(f"SCADA: {c.id} locked out")
        if ev.partial and any(ev.partial.get(t) for t in c.out):
            r.append("partial-power reports point to an open conductor")
        on = [t for t in c.out if ev.probes.get(t) is True]
        off = [t for t in c.out if ev.probes.get(t) is False]
        if off:
            r.append(f"customer on {off[0]} confirmed their power is off")
        near = [self.feeder.transformers[t] for t in c.out]
        outside_on = [t for t, v in ev.probes.items() if v and t not in c.out and any(
            haversine_m((self.feeder.transformers[t].lat, self.feeder.transformers[t].lon), (x.lat, x.lon)) < 600
            for x in near)]
        if outside_on:
            r.append(f"customer on {outside_on[0]} confirmed power is on next door")
        if silent and c.kind != "xfmr_fuse":
            r.append(f"{len(silent)} transformers in its zone silent so far")
        if on:
            r.append(f"but a customer on {on[0]} says their power is on")
        return r
