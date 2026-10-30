"""The live call copilot: helps a human call-taker on the hard calls the agent puts through.

When the agent hands a live call over (live wire, fire, critical customer), the call stays on the same realtime Voice
Transcribe line, now heard with speaker diarization: the call-taker's words and the caller's are told apart as they
are spoken. The copilot shows the call-taker three things while they talk:

- the transcript, word by word, with who said what;
- the report filling itself in. Code reads each partial transcript at once (account numbers, house and street,
  hazard words) so a field appears while the caller is still speaking; when a turn ends Muse Spark reads everything
  the caller has said and the field is confirmed (or corrected), then code places the caller on the grid and looks up
  what the control room knows there: the customer, transformer, open outage, crew and restoration time, hazards
  already reported nearby;
- what to say next. Code lists what is still worth saying, most urgent first (safety, hazards, the address, medical
  equipment, the tracer's question about next door; after filing, the status and restoration time), each as a draft
  in the caller's language. Spark picks the one that helps most given the conversation and words it, with an English
  line for a call-taker who does not speak the caller's language. The same fact check as the agent's lines applies,
  and safety lines are never reworded.

Spark takes ~20 s per call with its reasoning (first live run: a turn to the next suggestion took up to 65 s when
reading and wording ran one after the other). So after every turn code's own reading and its top line (the template)
are shown at once and the call-taker can speak; Spark's reading and wording replace them when they arrive.

The call-taker decides: they say the suggestion (one click, spoken for them in this simulation), type their own line,
or speak into the microphone, which goes down the same line. Nothing is filed until they press File; the report then
goes through the same reading, placing and tracing as any other call. In this simulation the caller is played by the
World from the scenario's truth, as for the agent's calls.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from .callagent import FIXED, PURPOSE, SAFETY, facts_kept
from .extract import _keyword_fields
from .locales import HAZARD_NAMES

if TYPE_CHECKING:
    from .engine import Engine

SUGGEST_SYSTEM = """You help a human call-taker at an electricity utility's outage desk during a storm. The caller
speaks {language}. Code has listed what is still worth saying, most urgent first, each with a draft in {language}.
Choose the option that helps most given the conversation so far: safety before anything else, and never ask for
something the caller has already said. Word it the way a calm call-taker would say it aloud in {language}, in at most
two short sentences, keeping every number, time, street name and identifier in the draft exactly. An option marked
fixed must be said word for word. Return the option id, the line to say, the same line in English, and a few words
for the call-taker on why it comes next."""

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "option": {"type": "string"},
        "say": {"type": "string", "description": "the line to say, in the caller's language"},
        "en": {"type": "string", "description": "the same line in English"},
        "why_en": {"type": "string", "description": "a few words for the call-taker"},
    },
    "required": ["option", "say", "en", "why_en"],
}

ANSWER = {"ask_address": "address", "ask_hazard": "hazard"}  # acts the simulated caller answers from the truth
REVEALS = {"ask_address": {"street", "house_no", "account_no"}, "ask_hazard": {"hazard"}}
NO_REPLY = {"close", "status_enroute", "status_onsite", "status_waiting", "status_locating", "status_restored_dark"}
FREE_TEXT = (("ask_address", ("address", "street", "where", "house", "account", "dirección", "முகவரி", "ලිපිනය",
                              "पता")),
             ("ask_hazard", ("wire", "pole", "tree", "danger", "spark", "fire", "cable", "poste", "கம்பி", "වයර", "तार")),
             ("ask_medical", ("medical", "oxygen", "equipment", "médico", "oxígeno", "மருத்துவ", "වෛද්‍ය", "मेडिकल")))
FIELD_ORDER = ["hazard", "symptom", "account", "address", "customer", "critical", "transformer", "outage", "crew",
               "eta", "nearby"]


class Copilot:
    def __init__(self, engine: Engine, call_id: str) -> None:
        p = engine.parked[call_id]
        self.e, self.id, self.why = engine, call_id, p["why"]
        self.event, self.call = p["event"], p["call"]
        self.lang = self.call["language"]
        self.agent = engine.agent
        self.line = self.agent.lines.get(call_id)
        if self.line is not None:
            self.line.on_event = self._on_line(self.line.on_event)
        # What the agent read before the hand-over: the copilot starts from it instead of reading again.
        self.p_model = p.get("model", "Code")
        self.f: dict = p.get("fields") or {}
        self.loc: dict = p.get("loc") or {}
        self.refining = False
        self._thinking: asyncio.Future | None = None
        self.fields: dict[str, dict] = {}
        self.asked: set[str] = set()
        self.revealed: set[str] = set()
        self.options: list[dict] = []
        self.suggestion: dict | None = None
        self.status = "talking"  # -> filed -> ended
        self.msg: dict | None = None
        self.busy = False
        self.mic_partial = ""

    # ---- state for the console ---------------------------------------------------------------

    def state(self) -> dict:
        return {"id": self.id, "language": self.lang, "status": self.status, "why": self.why, "busy": self.busy,
                "refining": self.refining,
                "fields": [{"name": k, **self.fields[k]} for k in FIELD_ORDER if k in self.fields],
                "suggestion": self.suggestion, "options": [{k: o[k] for k in ("act", "why", "fixed")}
                                                           for o in self.options],
                "incident": (self.msg or {}).get("incident"), "mic": bool(self.line and self.line.live),
                "listener": "Voice Transcribe (realtime, diarization)" if self.line and self.line.live
                else "mock (script)", "mic_partial": self.mic_partial}

    async def _push(self) -> None:
        await self.e.broadcast({"type": "copilot", "state": self.state()})

    async def begin(self) -> None:
        await self.e.log("Operator", f"{self.id}: call-taker on the line, copilot assisting", self.why, self.id)
        self._fill(self.p_model)
        await self._think(read=False)

    async def _think(self, read: bool = True) -> None:
        """After every turn: code's reading and top line at once, then Spark's reading and wording when they come."""
        if self._thinking is not None:
            self._thinking.cancel()
        if read:
            self._code_read()
        self.options = self._options()
        self.suggestion = self._template() if self.options else None
        if not self.options:
            await self._suggest()
        await self._push()
        self._thinking = asyncio.ensure_future(self._refine(read))

    async def _refine(self, read: bool) -> None:
        self.refining = True
        await self._push()
        try:
            if read:
                await self._read()
            await self._suggest()
        except asyncio.CancelledError:
            return  # the call-taker spoke first; a new turn starts its own refinement
        finally:
            self.refining = False
        await self._push()

    # ---- the report filling itself in -------------------------------------------------------

    def _caller_text(self) -> str:
        return " ".join(t["text"] for t in self.call["turns"] if t["who"] == "caller" and t["text"] != "…")

    def _set(self, name: str, value, by: str, live: bool = False) -> None:
        if value in (None, "", "none") and name != "hazard":
            return
        old = self.fields.get(name)
        if live and old and not old.get("live"):
            return  # a partial transcript never overrides what a model has read
        self.fields[name] = {"value": str(value), "by": by, "live": live,
                             "changed": bool(old and old["value"] != str(value))}

    def _quick(self, partial: str) -> None:
        """Code reads a partial transcript at once: hazard words, house and street, account number."""
        heard = f"{self._caller_text()} {partial}"
        k = _keyword_fields(heard, self.lang)
        if k["hazard"] != "none":
            self._set("hazard", k["hazard"].replace("_", " "), "Code (live)", live=True)
        if k.get("street") and k.get("house_no"):
            self._set("address", self.agent.address(k["house_no"], k["street"]), "Code (live)", live=True)
        if (m := re.search(r"\b\d{8,12}\b", heard)) and (c := self.e.db.by_account(m.group(0))):
            self._set("account", c.account_no, "Code (live)", live=True)

    def _code_read(self) -> None:
        """Code's reading of everything the caller has said, over Spark's last reading (no model, instant)."""
        k = _keyword_fields(self._caller_text(), self.lang)
        f = dict(self.f) if self.f else {**k, "landmark": None}  # the keyword parser's landmark is the whole text
        for n in ("street", "house_no", "account_no", "hazard"):
            if f.get(n) in (None, "none", "") and k.get(n) not in (None, "none", ""):
                f[n] = k[n]
        self.f = f
        self.loc = (self.e._locate(f, self.event.get("from")) if not f.get("is_junk") else None) or {}
        self._fill("Code (live)")

    async def _read(self) -> None:
        """Spark reads all the caller has said; code places them and looks up what the control room knows."""
        e, eng = self.event, self.e
        withheld = set(e.get("withheld", ())) - self.revealed
        ext = await eng._extract(self._caller_text() or e["text"],
                                 {**e, "truth": {k: v for k, v in e.get("truth", {}).items() if k not in withheld}})
        eng._count(ext.model)
        self.f = ext.fields
        self.loc = (eng._locate(self.f, e.get("from")) if not self.f["is_junk"] else None) or {}
        self._fill(ext.model)
        self.options = self._options()

    def _fill(self, by: str) -> None:
        """Show what was read and what the control room knows at that place."""
        eng, f, loc = self.e, self.f, self.loc
        if not f:
            return
        self._set("hazard", (f.get("hazard") or "none").replace("_", " "), by)
        self._set("symptom", (f.get("symptom") or "none").replace("_", " "), by)
        if loc.get("transformer"):
            where = (self.agent.address(loc["house_no"], loc["street"]) if loc.get("house_no") and loc.get("street")
                     else loc.get("street") or loc["method"].replace("landmark: ", "near "))
            self._set("address", where, f"Code (located by {loc['method'].split(':')[0]})")
            self._set("transformer", loc["transformer"], "Code")
        customer = eng.db.by_account(loc["account"]) if loc.get("account") else None
        if customer:
            self._set("account", customer.account_no, "Code")
            self._set("customer", customer.name, "Code (customer database)")
            if customer.critical:
                self._set("critical", customer.critical, "Code (customer database)")
        act, kw = self.agent.status_line(loc, (self.msg or {}).get("incident"))
        inc = next((i for i in eng._active() if loc.get("transformer") in i["out"]), None)
        if inc:
            self._set("outage", f"{inc['id']} · {self.agent.kind_title.get(inc['kind'], inc['kind'])}", "Code (tracer)")
            crew = next((c["name"] for c in eng.crews.values() if c["incident"] == inc["id"]), None)
            self._set("crew", f"{crew} ({inc['status']})" if crew else "not assigned yet", "Code (dispatch)")
            if inc.get("eta"):
                self._set("eta", eng.clock(inc["eta"]), "Code (planner)")
        elif act == "status_restored_dark":
            self._set("outage", f"restored at {kw['at']}; still dark here: second fault?", "Code")
        if (known := self.agent._hazard_known(loc)) and f.get("hazard", "none") == "none":
            self._set("nearby", HAZARD_NAMES["en"][known] + " reported nearby", "Code (earlier calls)")

    # ---- what to say next -------------------------------------------------------------------

    def _options(self) -> list[dict]:
        """What is still worth saying, most urgent first, with its facts; code decides, Spark only words it."""
        out: list[dict] = []
        f, loc, asked = self.f, self.loc, self.asked

        def opt(act: str, why: str, keep: tuple = (), en_kw: dict | None = None, **kw) -> None:
            if act not in asked:
                out.append({"act": act, "why": why, "kw": kw, "en_kw": en_kw or kw, "keep": keep,
                            "fixed": act in FIXED})

        if self.status == "talking":
            hazard = f.get("hazard", "none")
            if hazard in SAFETY:
                opt(SAFETY[hazard], f"{hazard.replace('_', ' ')} reported: safety instruction first")
            if hazard == "none":
                if known := self.agent._hazard_known(loc):
                    opt("known_hazard", "a hazard is already reported nearby", what=HAZARD_NAMES[self.lang][known],
                        en_kw={"what": HAZARD_NAMES["en"][known]})
                else:
                    opt("ask_hazard", "no hazard mentioned yet")
            if not loc.get("transformer"):
                opt("ask_address", "the caller is not placed on the grid yet")
            elif loc.get("method") == "caller ID":
                opt("confirm_address", "address only known from caller ID",
                    address=self.agent.address(loc.get("house_no"), loc.get("street")), keep=(loc.get("street"),))
            customer = self.e.db.by_account(loc["account"]) if loc.get("account") else None
            if customer and customer.critical:
                opt("ask_medical", f"account flagged critical ({customer.critical}): confirm life-support load")
            if self.e.sim is not None and (q := self.agent.neighbour_target(loc.get("transformer"))):
                L, target, who = q
                opt("ask_neighbour", f"tracer is torn: {L.candidate.id} {L.confidence:.0%} vs "
                    f"{L.alternative.id} {L.alt_confidence:.0%}; next door tells them apart",
                    address=self.agent.address(who.house_no, who.street), keep=(who.street,))
            if not customer or not customer.critical:
                opt("ask_medical", "priority restoration if someone depends on medical equipment")
        else:
            act, kw = self.agent.status_line(loc, (self.msg or {}).get("incident"))
            opt(act, "tell the caller what the control room knows", keep=tuple(v for v in kw.values()), **kw)
            opt("close", "nothing else to ask")
        return out

    def _draft(self, o: dict, lang: str | None = None) -> str:
        return self.e.loc["agent"][lang or self.lang][o["act"]].format(**(o["kw"] if lang is None else o["en_kw"]))

    def _template(self) -> dict:
        top = self.options[0]
        return {"act": top["act"], "say": self._draft(top), "en": self._draft(top, "en"), "why": top["why"],
                "model": "Code (template)"}

    async def _suggest(self) -> None:
        self.options = self._options()
        if not self.options:
            self.suggestion = {"act": "file", "say": "", "en": "", "why": "location and hazards are known: file the "
                               "report", "model": "Code"}
            return
        pick = self._template()
        if not self.e.offline and not (self.options[0]["fixed"] and len(self.options) == 1):
            pick = await self._spark({**pick, "model": "mock (template)"})
        self.suggestion = pick

    async def _spark(self, fallback: dict) -> dict:
        transcript = "\n".join(f"{t['who']}: {t['text']}" for t in self.call["turns"])
        options = "\n".join(f"- id {o['act']}{' (fixed)' if o['fixed'] else ''}: {PURPOSE.get(o['act'], o['act'])}"
                            f"; code's reason: {o['why']}; draft: {self._draft(o)}" for o in self.options)
        schema = {**SUGGEST_SCHEMA, "properties": {**SUGGEST_SCHEMA["properties"],
                                                    "option": {"type": "string",
                                                               "enum": [o["act"] for o in self.options]}}}
        system = SUGGEST_SYSTEM.format(language=self.agent.lang_name.get(self.lang, "English"))
        try:
            out = await asyncio.to_thread(self.e.client.spark_json, system,
                                          f"Conversation so far:\n{transcript}\n\nOptions:\n{options}", schema,
                                          "NextLine")
        except Exception:  # noqa: BLE001
            out = None
        if not out:
            return fallback
        self.e._count("Muse Spark")
        o = next((o for o in self.options if o["act"] == out.get("option")), self.options[0])
        draft, en = self._draft(o), self._draft(o, "en")
        pick = {"act": o["act"], "why": out.get("why_en") or o["why"], "model": "Muse Spark"}
        if o["fixed"]:
            return {**pick, "say": draft, "en": en, "model": "Muse Spark (choice) · fixed text"}
        if dropped := facts_kept(draft, out.get("say", ""), o["keep"]):
            return {**pick, "say": draft, "en": en, "model": "Code (Spark line failed fact check)", "rejected": dropped}
        return {**pick, "say": out["say"].strip(), "en": out.get("en") or en}

    # ---- the call-taker's actions ----------------------------------------------------------------

    async def say(self, act: str | None = None, text: str | None = None) -> dict:
        """The call-taker says the suggestion, another listed line, or their own words; the caller answers."""
        if self.busy or self.status == "ended":
            return {"ok": False, "error": "busy"}
        self.busy = True
        try:
            s = self.suggestion or {}
            if text:
                act, en, by = self._classify(text), None, "Call-taker"
            elif act == s.get("act") and s.get("say"):
                text, en, by = s["say"], s["en"], f"Call-taker · copilot line ({s['model']})"
            elif o := next((o for o in self.options if o["act"] == act), None):
                text, en, by = self._draft(o), self._draft(o, "en"), "Call-taker · copilot line (template)"
            else:
                return {"ok": False, "error": "nothing to say"}
            self.suggestion = None
            self.call["turns"].append({"who": "taker", "act": act or "free", "text": text, "en": en, "model": by})
            self.call["acts"].append(act or "free")
            if act:
                self.asked.add(act)
            await self._push()
            if self._thinking is not None:
                self._thinking.cancel()
            await self._spoken()
            await self._reply(act)
        finally:
            self.busy = False
        await self._think()
        return {"ok": True}

    async def _spoken(self) -> None:
        """The call-taker's line goes down the phone line (synthesised here; a microphone in real use)."""
        i = len(self.call["turns"]) - 1
        await self.e.broadcast({"type": "live_turn", "id": self.id, "i": i, "turn": self.call["turns"][i]})
        if self.call.get("live"):
            await self.agent._hear_live(self.call, len(self.call["turns"]) - 1)

    def _classify(self, text: str) -> str | None:
        t = text.lower()
        return next((act for act, words in FREE_TEXT if any(w in t for w in words)), None)

    async def _reply(self, act: str | None) -> None:
        """The simulated caller answers from the scenario's truth (as for the agent's questions)."""
        sim, e = self.e.sim, self.event
        if sim is None or act in NO_REPLY:
            return
        words = sim._words(e)
        if act in ANSWER:
            answer = sim.answer(e, ANSWER[act])
        elif act == "ask_medical":
            truth = e.get("truth", {})
            c = self.e.db.by_account(truth.get("account_no") or self.loc.get("account") or "")
            answer = words["medical_yes" if c and c.critical else "medical_no"]
        elif act == "ask_neighbour" and (q := self.agent.neighbour_target(self.loc.get("transformer"))):
            L, target, who = q
            answer, on = sim.neighbour(e, who)
            question = self.call["turns"][-1]["text"]
            await self.agent.hear(self.call, answer, "Simulated caller")
            async with self.e.lock:
                await self.agent.neighbour_answer(self.id, self.lang, e.get("from"), L, target, who, question,
                                                  self.call["turns"][-1]["text"], on)
            return
        else:
            answer = words["yes"]
        self.revealed |= REVEALS.get(act, set())
        await self.agent.hear(self.call, answer, "Simulated caller")

    async def file(self) -> dict:
        if self.status != "talking":
            return {"ok": False, "error": "already filed"}
        async with self.e.lock:
            self.msg = await self.e.file_call(self.id, self._caller_text() or self.event["text"], self.revealed)
        self.status = "filed"
        await self._think()
        return {"ok": True, "incident": self.msg.get("incident")}

    async def end(self) -> dict:
        while self.busy:
            await asyncio.sleep(0.2)
        if self.status == "talking":
            await self.file()
        if self._thinking is not None:
            self._thinking.cancel()
        self.status = "ended"
        if self.call.get("live"):
            await self.agent.end_live(self.call)
        self.e.copilots.pop(self.id, None)
        await self._push()
        await self.e.broadcast({"type": "call", "id": self.id, "call": self.call,
                                "incident": (self.msg or {}).get("incident")})
        await self.e.note("Operator", f"{self.id}: call ended by the call-taker",
                          " → ".join(a.replace("_", " ") for a in self.call["acts"]), self.id)
        return {"ok": True}

    # ---- the realtime line: partial transcripts and the call-taker's microphone ---------------------

    def _on_line(self, inner):
        async def on_event(ev: dict) -> None:
            if inner:
                await inner(ev)
            hearing = self.call.get("_hearing")
            if ev["role"] == "caller" and ev["kind"] == "partial" and hearing is not None:
                self._quick(ev["text"])
                await self._push()
            elif ev["role"] == "mic" and hearing is None and not self.busy:
                # The call-taker speaking into the microphone: shown as it is heard; a finished turn is their line.
                self.mic_partial = "" if ev["kind"] == "final" else ev["text"]
                await self._push()
                if ev["kind"] == "final" and ev["text"].strip():
                    asyncio.ensure_future(self._mic_turn(ev["text"], ev.get("speaker")))
        return on_event

    async def _mic_turn(self, text: str, speaker: str | None) -> None:
        if self.busy:
            return
        self.busy = True
        try:
            act = self._classify(text)
            model = "Call-taker (microphone) · Voice Transcribe (realtime)" + (f", speaker {speaker}" if speaker else "")
            self.call["turns"].append({"who": "taker", "act": act or "free", "text": text, "model": model})
            self.call["acts"].append(act or "free")
            if act:
                self.asked.add(act)
            await self.e.broadcast({"type": "live_turn", "id": self.id, "i": len(self.call["turns"]) - 1,
                                    "turn": self.call["turns"][-1]})
            await self._reply(act)
        finally:
            self.busy = False
        await self._think()

    def mic(self, pcm: bytes) -> bool:
        if self.line is None or not self.line.live:
            return False
        self.line.mic(pcm)
        return True
