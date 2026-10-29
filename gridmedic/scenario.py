"""Scenario replay: streams a scripted storm into the engine in (accelerated) real time,
and plays the customers who answer the agent's questions.
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

PROBE_REPLY_DELAY_S = 45
REPLY = {
    True: {"en": "Yes, our power is on.", "si": "ඔව්, අපේ ගෙදර විදුලිය තියෙනවා.",
           "ta": "ஆம், எங்கள் வீட்டில் மின்சாரம் உள்ளது."},
    False: {"en": "No, we have no power here either.", "si": "නැහැ, අපිටත් විදුලිය නැහැ.",
            "ta": "இல்லை, எங்களுக்கும் மின்சாரம் இல்லை."},
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


def truth_outage(sc: dict) -> set[str]:
    """Transformers actually without power in the scripted storm (used only to answer questions)."""
    feeder = get_feeder()
    out: set[str] = set()
    for f in sc["faults"]:
        dev = f["device"]
        if dev.startswith("LINE-"):
            sid = dev[5:]
            out |= {t for s in feeder.sections_below(sid) for t, x in feeder.transformers.items() if x.section == s}
        else:
            out |= feeder.downstream[dev]
    return out


class Replayer:
    def __init__(self, scenario: dict, handle) -> None:
        self.sc = scenario
        self.handle = handle
        self.speed = 10.0
        self.task: asyncio.Task | None = None
        self.out = truth_outage(scenario)
        self.reset()

    def reset(self) -> None:
        self.clock = 0.0
        self.running = False
        self._seq = itertools.count()
        self.queue = [(e["t"], next(self._seq), e) for e in self.sc["events"]]
        heapq.heapify(self.queue)

    def schedule_probe_reply(self, probe: dict) -> None:
        on = probe["transformer"] not in self.out
        lang = probe["language"]
        e = {"t": probe["t"] + PROBE_REPLY_DELAY_S, "type": "complaint", "id": f"{probe['id']}-reply",
             "channel": "whatsapp", "language": lang, "from": probe["to"], "text": REPLY[on][lang],
             "probe_reply": probe["id"],
             "truth": {"street": probe["street"], "house_no": probe["house_no"],
                       "symptom": "power_on" if on else "no_power", "hazard": "none"}}
        heapq.heappush(self.queue, (e["t"], next(self._seq), e))

    async def run(self, on_tick) -> None:
        self.running = True
        last = time.monotonic()
        while self.running and (self.queue or self.clock < self.sc["duration_s"]):
            now = time.monotonic()
            self.clock = min(self.clock + (now - last) * self.speed, self.sc["duration_s"])
            last = now
            while self.queue and self.queue[0][0] <= self.clock:
                _, _, e = heapq.heappop(self.queue)
                await self.handle(e)
                last = time.monotonic()  # model latency does not eat scenario time
            await on_tick(self.clock)
            if self.clock >= self.sc["duration_s"] and not self.queue:
                break
            await asyncio.sleep(0.1)
        self.running = False
