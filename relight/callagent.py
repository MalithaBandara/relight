"""The call agent: answers every outage call, in the caller's language.

Voice Transcribe hears the caller and Muse Spark reads what they said (Engine._complaint). This module decides, in
code, what the agent says next, from what the control room knows and nothing else: the caller's account and address,
open incidents with their crews and restoration times, earlier reports, hazards, restorations, and the tracer's open
questions. A caller whose answer would separate two rival explanations of an outage is asked about the houses next
door, and the answer becomes evidence like any SMS reply. Questions are answered by the simulated World, the same way
customers answer the agent's SMS questions.

Spark may reword a status reply on a voiced call so it sounds natural; safety instructions are fixed text, never
reworded, and calls about live wires, fires or critical customers are flagged to the control room.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .grid import haversine_m
from .locales import HAZARD_NAMES

if TYPE_CHECKING:
    from .engine import Engine

TRANSCRIBE_LANGS = {"en", "ta", "hi", "es"}  # of ours, the ones in Voice Transcribe's 25; Sinhala is not
SAFETY = {"live_wire": "safety_live", "wire_down": "safety_live", "pole_down": "safety_down",
          "tree_on_line": "safety_down", "fire": "safety_fire"}
ESCALATE = {"live_wire", "fire"}
LINE_DAMAGE = {"pole_down", "tree_on_line", "live_wire", "wire_down"}
HAZARD_NEAR_M = 250  # a hazard already reported this close needs no question
NEIGHBOUR_M = 400  # houses a caller can be expected to know about
CREW_STATE = {"dispatched": "enroute", "on site": "onsite"}

REPLY_SYSTEM = """You are the voice of an electricity utility's outage desk on a phone call. Reword the reply you are
given so it sounds natural when spoken, in {language} and its usual script. Keep every fact exactly as given (times,
numbers, fault type, street names) and add nothing. At most two short sentences. Return only the reply."""


class CallAgent:
    def __init__(self, engine: Engine, kind_title: dict[str, str], lang_name: dict[str, str]) -> None:
        self.e = engine
        self.loc = engine.loc
        self.kind_title, self.lang_name = kind_title, lang_name

    # ---- turns -------------------------------------------------------------------------

    def start(self, e: dict, text: str | None, model: str) -> dict:
        lang = e.get("language") if e.get("language") in self.loc["agent"] else "en"
        voices = self.loc["voices"]
        callers = voices["caller"].get(e.get("language"), voices["caller"]["en"])
        caller = e.get("voice") or callers[sum(map(ord, e.get("from") or e["id"])) % len(callers)]
        call = {"language": lang, "turns": [], "acts": [], "escalated": False,
                "voices": {"agent": voices["agent"][lang], "caller": caller}}
        self.say(call, "greet")
        if text is not None:
            self.hear(call, text, model, e.get("audio"))
        return call

    def say(self, call: dict, act: str, text: str | None = None, model: str = "Agent", en_kw: dict | None = None,
            **kw) -> None:
        en = self.loc["agent"]["en"][act].format(**(en_kw or kw))
        call["turns"].append({"who": "agent", "act": act, "model": model, "en": en,
                              "text": text or self.loc["agent"][call["language"]][act].format(**kw)})
        call["acts"].append(act)

    def hear(self, call: dict, text: str, model: str, audio: str | None = None) -> None:
        call["turns"].append({"who": "caller", "text": text, "model": model, "audio": audio})

    def address(self, house, street) -> str:
        return self.loc["address"].format(house=house, street=street)

    # ---- during the call, before the report is filed --------------------------------------

    async def questions(self, call: dict, e: dict, fields: dict, loc: dict) -> str | None:
        """Confirm or ask for the address, and ask about hazards. Returns what the caller added, if anything."""
        eng, sim = self.e, self.e.sim
        key = loc.get("account") or e.get("from") or e["id"]
        if sim is None or e.get("followup") or key in eng.seen:
            return None  # a repeat or follow-up caller only needs the status
        said = []
        if loc.get("method") == "caller ID":
            self.say(call, "confirm_address", address=self.address(loc.get("house_no"), loc.get("street")))
            self.hear(call, sim.answer(e, "yes"), "Simulated caller")
        elif not loc.get("transformer"):
            self.say(call, "ask_address")
            said.append(sim.answer(e, "address"))
            self.hear(call, said[-1], "Simulated caller")
        if fields["hazard"] == "none":
            if known := self._hazard_known(loc):
                # Earlier callers already reported it: warn this one instead of asking.
                self.say(call, "known_hazard", what=HAZARD_NAMES[call["language"]][known],
                         en_kw={"what": HAZARD_NAMES["en"][known]})
            elif e.get("audio") or not eng.pack.get("quiet_messages"):  # in a surge, keep unvoiced calls short
                self.say(call, "ask_hazard")
                said.append(sim.answer(e, "hazard"))
                self.hear(call, said[-1], "Simulated caller")
        return " ".join(said) or None

    def _hazard_known(self, loc: dict) -> str | None:
        """The kind of hazard already reported near this caller, if any."""
        if loc.get("lat") is None:
            return None
        near = [h for h in self.e.hazards if not h.get("safe") and h["kind"] in HAZARD_NAMES["en"]
                and haversine_m((h["lat"], h["lon"]), (loc["lat"], loc["lon"])) < HAZARD_NEAR_M]
        if near:
            return near[0]["kind"]
        xf = loc.get("transformer")
        return next((i["kind"] for i in self.e._active() if xf in i["out"] and i["kind"] in LINE_DAMAGE), None)

    async def not_understood(self, call: dict, e: dict, model: str) -> None:
        """No model could read the call (e.g. Sinhala audio): ask the caller to send the breakdown SMS instead."""
        self.hear(call, "…", model, e.get("audio"))
        self.say(call, "sms_fallback", code=self.loc["sms_label"].split()[0])
        self.say(call, "close")
        await self.e.log("Agent", f"{e['id']}: call not understood ({self.lang_name.get(e.get('language'), '?')})",
                         "asked the caller to send the breakdown SMS instead", e["id"])
        await self.e.broadcast({"type": "call", "id": e["id"], "call": call})
        if self.e.sim:
            self.e.sim.sms_fallback(e, self.e.elapsed)

    # ---- after the report is filed: safety, a question for the tracer, status ---------------

    async def finish(self, msg: dict) -> None:
        eng, call, f = self.e, msg["call"], msg["fields"]
        loc = msg.get("location") or {}
        if msg["status"] == "junk":
            self.say(call, "junk")
        else:
            if msg["status"] == "duplicate":
                first = next((m for m in eng.messages if m["id"] == msg.get("dup_of")), None)
                if first:
                    self.say(call, "repeat", at=eng.clock(first["t"]))
            hazard = f.get("hazard")
            if hazard in SAFETY:
                self.say(call, SAFETY[hazard])
            customer = eng.db.by_account(loc["account"]) if loc.get("account") else None
            urgent = (hazard.replace("_", " ") + " reported") if hazard in ESCALATE else (
                f"critical customer ({customer.critical})" if customer and customer.critical else None)
            if urgent:
                call["escalated"] = True
                self.say(call, "escalate")
                await eng.log("Agent", f"{msg['id']}: urgent call flagged to the control room", urgent, msg["id"])
            if msg["status"] != "duplicate" and not msg.get("followup") and eng.sim:
                await self._neighbour(msg)
            await self._status(msg)
        self.say(call, "close")
        await eng.broadcast({"type": "call", "id": msg["id"], "call": call, "incident": msg.get("incident")})
        await eng.note("Agent", f"{msg['id']}: call answered ({self.lang_name.get(msg['language'], msg['language'])})",
                       " → ".join(a.replace("_", " ") for a in call["acts"]), msg["id"])

    async def _status(self, msg: dict) -> None:
        eng, call = self.e, msg["call"]
        loc = msg.get("location") or {}
        xf, acct = loc.get("transformer"), loc.get("account")
        inc = next((i for i in eng._active() if i["id"] == msg.get("incident") or (xf and xf in i["out"])
                    or (acct and acct in i["dead_customers"])), None)
        if inc:
            act = "status_" + CREW_STATE.get(inc["status"], "waiting")
            kind = "cause still being checked" if inc["kind"] == "unknown" else self.kind_title[inc["kind"]].lower()
            kw = {"kind": kind, "eta": eng.clock(inc["eta"]) if inc["eta"] else "–"}
        elif xf in eng.restored_at:
            act, kw = "status_restored_dark", {"at": eng.clock(eng.restored_at[xf])}
        else:
            act, kw = "status_locating", {}
        text = self.loc["agent"][call["language"]][act].format(**kw)
        model = "Agent"
        if msg["event"].get("audio"):
            text, model = await self._phrase(call["language"], text)
            eng._count(model)
        self.say(call, act, text=text, model=model, **kw)

    async def _phrase(self, lang: str, text: str) -> tuple[str, str]:
        """Spark rewords a status reply for a voiced call; the template stands in when it cannot."""
        out = None
        if not self.e.offline:
            try:
                out = await asyncio.to_thread(self.e.client.spark_text,
                                              REPLY_SYSTEM.format(language=self.lang_name.get(lang, "English")),
                                              f"Reply: {text}")
            except Exception:  # noqa: BLE001
                out = None
        return (out.strip(), "Muse Spark") if out else (text, "mock (template)")

    async def _neighbour(self, msg: dict) -> None:
        """If the tracer is torn between two explanations that differ next door, ask the caller about next door."""
        from .engine import ASK_BELOW, PROBE_GAP_S

        eng, call = self.e, msg["call"]
        xf = (msg.get("location") or {}).get("transformer")
        if not xf:
            return
        here = eng.feeder.transformers[xf]
        claimed = {t for i in eng._active() for t in i["out"]}
        for L in eng.located:
            if L.confidence >= ASK_BELOW or L.alternative is None:
                continue
            c, alt = L.candidate, L.alternative
            if xf not in c.out | alt.out or any(
                    p["fault"] == c.id and (p.get("answer") is None or eng.elapsed - p["t"] < PROBE_GAP_S)
                    for p in eng.probes):
                continue
            diff = (c.out ^ alt.out) - set(eng.ev.reports) - set(eng.ev.probes) - claimed - {xf}
            near = sorted((haversine_m((here.lat, here.lon), (t.lat, t.lon)), t.id)
                          for t in (eng.feeder.transformers[x] for x in diff))
            target = next((t for d, t in near if d < NEIGHBOUR_M
                           and any(not x.critical for x in eng.db.customers_on(t))), None)
            if target is None:
                continue
            who = min((x for x in eng.db.customers_on(target) if not x.critical),
                      key=lambda x: haversine_m((here.lat, here.lon), (x.lat, x.lon)))
            address = self.address(who.house_no, who.street)
            self.say(call, "ask_neighbour", address=address)
            answer, on = eng.sim.neighbour(msg["event"], who)
            self.hear(call, answer, "Simulated caller")
            probe = {"id": f"Q{len(eng.probes) + 1}", "t": round(eng.elapsed), "fault": c.id, "rival": alt.id,
                     "transformer": target, "to": msg.get("from"), "name": who.name, "street": who.street,
                     "house_no": who.house_no, "language": msg["language"], "text": call["turns"][-2]["text"],
                     "answer": None, "lat": who.lat, "lon": who.lon, "via": msg["id"]}
            eng.probes.append(probe)
            await eng.log("Agent", f"Asked caller {msg['id']} about {address} (transformer {target})",
                          f"{c.id} {L.confidence:.0%} vs {alt.id} {L.alt_confidence:.0%}: next door separates the two",
                          probe["id"])
            await eng.broadcast({"type": "probe", "probe": probe})
            # The answer is read like any other message (Spark, or its label in mock mode) and becomes evidence.
            await eng._complaint({"t": eng.elapsed, "type": "complaint", "id": f"{msg['id']}-{probe['id']}",
                                  "channel": "call", "language": msg["language"], "text": answer,
                                  "probe_reply": probe["id"],
                                  "truth": {"street": who.street, "house_no": who.house_no, "hazard": "none",
                                            "symptom": "power_on" if on else "no_power"}})
            await eng.recompute()
            return
