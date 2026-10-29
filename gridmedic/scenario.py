"""Scenario replay and the simulated physical world.

The Replayer streams a scripted storm into the engine in (accelerated) real time.
The World holds the physical truth GridMedic never sees directly: which sections are
broken, which fuses blew, which service wires are down. It plays everyone outside
the control room: customers answering the agent's questions, crews reporting what
they find on site, and customers who are still dark after a repair (which is how a
hidden second fault shows itself).
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import json
import time

from .config import SCENARIO_DIR
from .customers import CustomerDB
from .grid import get_feeder
from .network import NetworkState, live_transformers

PROBE_REPLY_DELAY_S = 45
FOLLOWUP_DELAYS_S = (120, 210, 330)
TIMELAPSE_SPEED = 240  # after the last scripted event, crews work through the night quickly
MAX_CLOCK_S = 10 * 3600

REPLY = {
    True: {"en": "Yes, our power is on.", "si": "ඔව්, අපේ ගෙදර විදුලිය තියෙනවා.",
           "ta": "ஆம், எங்கள் வீட்டில் மின்சாரம் உள்ளது."},
    False: {"en": "No, we have no power here either.", "si": "නැහැ, අපිටත් විදුලිය නැහැ.",
            "ta": "இல்லை, எங்களுக்கும் மின்சாரம் இல்லை."},
}
FOLLOWUP = {
    "en": "The neighbours have power again but our house is still dark. {street} {house}.",
    "si": "අසල්වැසියන්ට විදුලිය ආවා, අපිට තවම නැහැ. {street} {house}.",
    "ta": "பக்கத்து வீடுகளுக்கு மின்சாரம் வந்துவிட்டது, எங்களுக்கு இன்னும் இல்லை. {street} {house}.",
}
SITE_REPORT = {
    "pole_down": "On site at {street} near number {house}. Concrete pole snapped, conductors down across the road. "
                 "Starting pole replacement.",
    "tree_on_line": "On site at {street} near number {house}. A tree is lying across the conductors. "
                    "Clearing it before the line work.",
    "live_wire": "On site at {street} near number {house}. The conductor on the road is live. Area cordoned off, "
                 "making it safe now.",
    "blown_fuse": "On site at transformer {xf} on {street} near number {house}. The drop-out fuse is blown. "
                  "Replacing it now.",
    "service_wire": "On site at {street} near number {house}.",
}
CONTRADICT = {
    "service_wire": "Transformer {xf} on {street} is fine, its fuses are intact. The service wire is down at "
                    "number {house} after a branch fell, so only houses {a} to {b} have no supply. Need a line crew "
                    "for the service wire.",
    "blown_fuse": "The line is fine here. It is the drop-out fuse on transformer {xf} near {street} number {house} "
                  "that has blown.",
}


def load(name: str = "galle_storm") -> dict:
    """Load a scenario and resolve each sender's phone and account from the customer database."""
    sc = json.loads((SCENARIO_DIR / f"{name}.json").read_text(encoding="utf-8"))
    db = CustomerDB()
    for e in sc["events"]:
        if e["type"] != "complaint":
            continue
        truth = e.get("truth", {})
        cust = None
        if truth.get("account_no") and truth["account_no"] != "@":
            cust = db.by_account(truth["account_no"])
        elif truth.get("street") and truth.get("house_no"):
            cust, _ = db.by_address(truth["street"], truth["house_no"])
        if cust:
            if truth.get("account_no") == "@":
                truth["account_no"] = cust.account_no
            e.setdefault("from", cust.phone)
            e["text"] = e["text"].replace("{account}", cust.account_no)
    sc["events"].sort(key=lambda e: e["t"])
    return sc


class World:
    """Physical truth of the storm: faults, device states, who actually has power."""

    def __init__(self, sc: dict) -> None:
        self.feeder = get_feeder()
        self.db = CustomerDB()
        self.faults = {f["id"]: dict(f) for f in sc["faults"]}
        self.state = NetworkState(open=set(self.feeder.normally_open))
        for f in self.faults.values():
            f["repaired"] = False
            if "section" in f:
                self.state.faulted.add(f["section"])
            elif f["kind"] == "service_wire":
                lo, hi = f["houses"]
                self.state.dead_customers |= {c.account_no for c in self.db.customers_on(f["transformer"])
                                              if lo <= c.house_no <= hi}
            elif "transformer" in f:
                self.state.dead_transformers.add(f["transformer"])

    def live(self) -> set[str]:
        return live_transformers(self.feeder, self.state)

    def has_power(self, account: str, transformer: str) -> bool:
        return transformer in self.live() and account not in self.state.dead_customers

    def switch(self, op: str, dev: str) -> None:
        (self.state.open.discard if op == "close" else self.state.open.add)(dev)

    def match(self, inc: dict) -> dict | None:
        """The real fault behind an incident GridMedic is working on."""
        live = [f for f in self.faults.values() if not f["repaired"]]
        if inc.get("site_xf"):
            hit = [f for f in live if f.get("transformer") == inc["site_xf"]]
            if hit:
                return hit[0]
        zone = set(inc.get("zone", []))
        hit = [f for f in live if f.get("section") in zone]
        if hit:
            return hit[0]
        out = set(inc.get("out", []))
        hit = [f for f in live if f.get("transformer") in out and not f.get("hidden")]
        return hit[0] if hit else None

    def site_report(self, inc: dict, crew: str) -> dict | None:
        """What the crew sees on arrival, as a crew_note event (text plus labels for mock mode)."""
        f = self.match(inc)
        if f is None:
            text = f"On site at {inc['label']}. No damage found here; the line looks healthy."
            return {"type": "crew_note", "crew": crew, "language": "en", "text": text, "incident": inc["id"],
                    "truth": {"damage": "none", "device_ok": True}}
        xf = f.get("transformer") or inc.get("site_xf") or ""
        vals = {"street": f["street"], "house": f.get("near_house", ""), "xf": xf,
                "a": f.get("houses", ["", ""])[0], "b": f.get("houses", ["", ""])[1]}
        believed = inc["kind"]
        if f["kind"] in CONTRADICT and believed not in ("unknown", f["kind"]):
            text = CONTRADICT[f["kind"]].format(**vals)
            device_ok = True
        else:
            text = SITE_REPORT[f["kind"]].format(**vals)
            device_ok = False
        truth = {"street": f["street"], "house_no": f.get("near_house"), "damage": f["kind"],
                 "device_ok": device_ok, "truth_fault": f["id"]}
        if f["kind"] == "service_wire":
            truth["house_from"], truth["house_to"] = f["houses"]
        return {"type": "crew_note", "crew": crew, "language": "en", "text": text, "incident": inc["id"],
                "truth": truth}

    def repair(self, fault_id: str) -> None:
        f = self.faults[fault_id]
        f["repaired"] = True
        self.state.faulted.discard(f.get("section"))
        if f["kind"] == "service_wire":
            lo, hi = f["houses"]
            self.state.dead_customers -= {c.account_no for c in self.db.customers_on(f["transformer"])
                                          if lo <= c.house_no <= hi}
        elif "transformer" in f:
            self.state.dead_transformers.discard(f["transformer"])

    def still_dark(self, transformers: list[str]) -> list:
        """Customers on these transformers who have no power in reality."""
        live = self.live()
        return [c for t in transformers for c in self.db.customers_on(t)
                if (t not in live or c.account_no in self.state.dead_customers) and not c.critical]


class Replayer:
    def __init__(self, scenario: dict, handle) -> None:
        self.sc = scenario
        self.handle = handle
        self.speed = 10.0
        self.task: asyncio.Task | None = None
        self.reset()

    def reset(self) -> None:
        self.clock = 0.0
        self.running = False
        self.world = World(self.sc)
        self._seq = itertools.count()
        self._ids = itertools.count(1)
        self.queue = [(e["t"], next(self._seq), e) for e in self.sc["events"]]
        heapq.heapify(self.queue)
        self.timelapse = False

    def push(self, e: dict) -> None:
        heapq.heappush(self.queue, (e["t"], next(self._seq), e))

    # ---- callbacks from the engine -----------------------------------------------

    def probe(self, probe: dict) -> None:
        c = self.world.db.by_phone(probe["to"])
        on = self.world.has_power(c.account_no, c.transformer_id) if c else True
        lang = probe["language"]
        self.push({"t": probe["t"] + PROBE_REPLY_DELAY_S, "type": "complaint", "id": f"{probe['id']}-reply",
                   "channel": "whatsapp", "language": lang, "from": probe["to"], "text": REPLY[on][lang],
                   "probe_reply": probe["id"],
                   "truth": {"street": probe["street"], "house_no": probe["house_no"],
                             "symptom": "power_on" if on else "no_power", "hazard": "none"}})

    def crew_arrived(self, inc: dict, crew: str, t: float) -> None:
        if (e := self.world.site_report(inc, crew)) is not None:
            e["t"], e["id"] = t, f"R{next(self._ids)}"
            self.push(e)

    def identify(self, inc: dict) -> str | None:
        """Scoring only: which real fault an incident corresponds to."""
        f = self.world.match(inc)
        return f["id"] if f else None

    def switched(self, op: str, dev: str) -> None:
        self.world.switch(op, dev)

    def repaired(self, inc: dict) -> str | None:
        f = self.world.match(inc)
        if f is None:
            return None
        self.world.repair(f["id"])
        return f["id"]

    def restored(self, transformers: list[str], t: float) -> None:
        """Customers who are still dark after GridMedic believes they are back will say so."""
        dark = self.world.still_dark(transformers)
        by_xf: dict[str, list] = {}
        for c in dark:
            by_xf.setdefault(c.transformer_id, []).append(c)
        for xf, cs in by_xf.items():
            for i, c in enumerate(cs[:: max(len(cs) // 3, 1)][:3]):
                lang = ("en", "si", "ta")[i % 3]
                self.push({"t": t + FOLLOWUP_DELAYS_S[i], "type": "complaint", "id": f"C{100 + next(self._ids)}",
                           "channel": ("call", "whatsapp", "sms")[i % 3], "language": lang, "from": c.phone,
                           "followup": True,
                           "text": FOLLOWUP[lang].format(street=c.street, house=c.house_no),
                           "truth": {"street": c.street, "house_no": c.house_no, "symptom": "no_power",
                                     "hazard": "none"}})

    # ---- clock ------------------------------------------------------------------------

    async def deliver(self, e: dict) -> None:
        if e["type"] == "scada" and e["event"] == "lockout":
            self.world.state.open.add(e["device"])
        if e["type"] == "complaint" and not e.get("probe_reply") and self._has_power_now(e):
            return  # scripted before switching gave them power back; they would not call
        await self.handle(e)

    def _has_power_now(self, e: dict) -> bool:
        truth = e.get("truth", {})
        if truth.get("symptom") not in ("no_power", "partial_power") or truth.get("customer_side"):
            return False
        c = self.world.db.by_account(truth["account_no"]) if truth.get("account_no") not in (None, "@") else None
        if c is None and truth.get("street") and truth.get("house_no"):
            c, _ = self.world.db.by_address(truth["street"], truth["house_no"])
        return bool(c) and self.world.has_power(c.account_no, c.transformer_id)

    async def run(self, on_tick, busy) -> None:
        """Advance the clock; `busy()` says whether crews still have work after the script ends."""
        self.running = True
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            scripted_left = any(e.get("t", 0) <= self.sc["duration_s"] for _, _, e in self.queue)
            self.timelapse = not scripted_left and self.clock >= self.sc["duration_s"]
            speed = max(self.speed, TIMELAPSE_SPEED) if self.timelapse else self.speed
            self.clock = min(self.clock + (now - last) * speed, MAX_CLOCK_S)
            last = now
            while self.queue and self.queue[0][0] <= self.clock:
                _, _, e = heapq.heappop(self.queue)
                await self.deliver(e)
                last = time.monotonic()  # model latency does not eat scenario time
            await on_tick(self.clock)
            if self.clock >= self.sc["duration_s"] and not self.queue and not busy():
                break
            if self.clock >= MAX_CLOCK_S:
                break
            await asyncio.sleep(0.1)
        self.running = False
