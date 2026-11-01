"""The call agent: answers every outage call, in the caller's language.

Voice Transcribe hears the caller and Muse Spark reads what they said (Engine._complaint). This module decides, in
code, what the agent says next, from what the control room knows and nothing else: the caller's account and address,
open incidents with their crews and restoration times, earlier reports, hazards, restorations, and the tracer's open
questions. A caller whose answer would separate two rival explanations of an outage is asked about the houses next
door, and the answer becomes evidence like any SMS reply. Questions are answered by the simulated World, the same way
customers answer the agent's SMS questions.

Code decides what to say (an act and its facts); Muse Spark says it, in the caller's language, the way a person
would. Every Spark line is checked before it is spoken: each number, time, street name and identifier in the
template must still be there, or the template is spoken instead. Without the API key the templates speak. Safety
instructions, the automated-assistant disclosure and the SMS fallback are fixed text and never reworded. Calls about
live wires, fires or critical customers are flagged to the control room.

Field crews report by phone or radio too, in their own language. The agent reads back what Spark understood (damage,
location, whether the device is healthy, houses out, crews needed), as is standard on utility radio, and Relight
changes nothing until the crew confirms; a crew that says "negative" repeats the report and it is read again.

Live calls (console switch): a voiced call is played out in real time, turn by turn, on one realtime Voice Transcribe
line (realtime.py). The caller's words show as they are spoken, the agent answers as soon as a turn ends, and its
lines are spoken on the same line. A live call the agent would escalate (live wire, fire, critical customer) is put
through to a human call-taker, whom the copilot (copilot.py) helps for the rest of the call.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Awaitable, Callable

from . import config, voice
from .grid import haversine_m
from .locales import HAZARD_NAMES, READBACK
from .realtime import REALTIME_LANGS, Line

if TYPE_CHECKING:
    from .engine import Engine

TRANSCRIBE_LANGS = {"en", "ta", "hi", "es"}  # of ours, the ones in Voice Transcribe's 25; Sinhala is not
SAFETY = {"live_wire": "safety_live", "wire_down": "safety_live", "pole_down": "safety_down",
          "tree_on_line": "safety_down", "fire": "safety_fire"}
FIXED = {"greet", "safety_live", "safety_down", "safety_fire", "known_hazard", "escalate", "sms_fallback", "close",
         "crew_text", "transfer"}  # never reworded by a model
ESCALATE = {"live_wire", "fire"}
LINE_DAMAGE = {"pole_down", "tree_on_line", "live_wire", "wire_down"}
HAZARD_NEAR_M = 250  # a hazard already reported this close needs no question
NEIGHBOUR_M = 400  # houses a caller can be expected to know about
CREW_STATE = {"dispatched": "enroute", "on site": "onsite"}
PURPOSE = {"confirm_address": "confirm the caller's address", "ask_address": "ask for the caller's address",
           "ask_hazard": "ask whether they can see fallen poles, wires or trees, and tell them not to go near",
           "ask_neighbour": "ask whether the houses next door have power", "repeat": "say they already reported it",
           "junk": "say this line is only for power outages", "readback": "read back the crew's report and ask if it "
           "is correct", "crew_changed": "acknowledge and say the diagnosis changed", "crew_logged": "acknowledge and "
           "say it is logged", "crew_unmatched": "acknowledge; no matching outage yet",
           "ask_medical": "ask whether anyone at the address uses medical equipment that needs power"}

SPEAK_SYSTEM = """You are the voice of an electricity utility's {desk} on a {line} call, speaking {language}.
You get a draft of what to say and its purpose. Say it the way a calm, courteous {person} would say it aloud in
{language}, in its usual script; common English technical words are fine if people say them that way.
Keep every number, time, street name and identifier exactly as written in the draft (same letters and digits).
Add no facts and drop none. At most two short sentences. Return only the words to speak."""


def crew_summary(f: dict, lang: str) -> str:
    """The structured crew report (Spark's reading) in plain words, for the read-back."""
    w = READBACK.get(lang, READBACK["en"])
    where = f.get("street") or f.get("landmark")
    if where and f.get("house_no"):
        where = w["near"].format(street=where, house=f["house_no"])
    parts = [w["at"].format(what=w["damage"].get(f.get("damage"), w["damage"]["other"]), where=where or w["here"])]
    if f.get("energised"):
        parts.append(w["live"])
    if f.get("device_ok"):
        parts.append(w["device_ok"])
    if f.get("house_from") is not None and f.get("house_to") is not None:
        parts.append(w["houses"].format(a=f["house_from"], b=f["house_to"]))
    if f.get("crew_needs"):
        parts.append(w["needs"].format(list=w["and"].join(w["crews"].get(c, c) for c in f["crew_needs"])))
    return w["sep"].join(parts)


def facts_kept(draft: str, said: str, keep: tuple[str, ...] = ()) -> list[str]:
    """Numbers, times and names from the draft that a model's rewording dropped or changed."""
    numbers = set(re.findall(r"\d+(?::\d+)?", draft))
    names = {k for k in keep if k}
    # whole tokens only: "23" must not pass inside "123", "6" inside "16", "I2" inside "I20"; a number may follow a
    # letter ("I2" in the draft yields "2", which the line may write as "I2")
    return sorted([n for n in numbers if not re.search(rf"(?<!\d){re.escape(n)}(?!\d)", said)] +
                  [k for k in names if not re.search(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", said,
                                                     re.IGNORECASE)])


class CallAgent:
    def __init__(self, engine: Engine, kind_title: dict[str, str], lang_name: dict[str, str]) -> None:
        self.e = engine
        self.loc = engine.loc
        self.kind_title, self.lang_name = kind_title, lang_name
        self.lines: dict[str, Line] = {}  # live calls in progress: their realtime transcription line
        self.live: dict[str, dict] = {}  # ... and the call itself, for the console's audio requests
        self._keywords: list[str] | None = None

    # ---- turns -------------------------------------------------------------------------

    def _lang(self, lang: str | None) -> str:
        return lang if lang in self.loc["agent"] else "en"

    async def start(self, e: dict, text: str | None, model: str) -> dict:
        lang = self._lang(e.get("language"))
        voices = self.loc["voices"]
        callers = voices["caller"].get(e.get("language"), voices["caller"]["en"])
        caller = e.get("voice") or callers[sum(map(ord, e.get("from") or e["id"])) % len(callers)]
        # Spark speaks on every call, except unvoiced calls during a surge (cost and time; templates instead).
        call = {"id": e["id"], "language": lang, "turns": [], "acts": [], "escalated": False, "line": "phone",
                "spark": bool(e.get("audio")) or not self.e.pack.get("quiet_messages"),
                "voices": {"agent": voices["agent"][lang], "caller": caller,
                           "taker": voices.get("taker", {}).get(lang, voices["agent"][lang])}}
        if self.e.live_calls and e.get("audio") and self.e.sim is not None:
            await self._open_line(call)
        await self.say(call, "greet")
        if text is not None:
            await self.hear(call, text, model, e.get("audio"))
        return call

    # ---- live calls: one realtime line per call, every turn spoken and heard in real time --------------

    def keywords(self) -> list[str]:
        """Street and landmark names for the realtime line's recognition bias (the streets with most customers)."""
        if self._keywords is None:
            rows = self.e.db.con.execute("SELECT street, COUNT(*) n FROM customers GROUP BY street ORDER BY n DESC")
            self._keywords = [lm["name"] for lm in self.e.db.landmarks][:20] + [r[0] for r in rows]
        return self._keywords

    async def _open_line(self, call: dict) -> None:
        line = Line(self.e.client, call["id"], call["language"], self.keywords(), self._on_line(call))
        await line.open()
        call["live"] = True
        self.lines[call["id"]], self.live[call["id"]] = line, call
        if line.error:
            await self.e.log("Code", f"{call['id']}: live call without realtime transcription", line.error, call["id"])
        await self.e.broadcast({"type": "live_call", "event": "start", "id": call["id"], "call": call,
                                "listener": "Voice Transcribe (realtime)" if line.live else "mock (script)"})

    def _on_line(self, call: dict):
        async def on_event(ev: dict) -> None:
            i = call.get("_hearing")
            if i is None or ev["role"] != call["turns"][i]["who"]:
                return  # the agent's own words coming back, or a turn already closed
            await self.e.broadcast({"type": "live_partial", "id": call["id"], "i": i, "text": ev["text"],
                                    "final": ev["kind"] == "final", "speaker": ev.get("speaker"),
                                    "model": ev.get("model", "Voice Transcribe (realtime)")})
        return on_event

    async def end_live(self, call: dict) -> None:
        if (line := self.lines.pop(call["id"], None)) is not None:
            await line.close()
        self.live.pop(call["id"], None)
        call.pop("_hearing", None)
        await self.e.broadcast({"type": "live_call", "event": "end", "id": call["id"], "call": call})

    async def _speak_live(self, call: dict, i: int) -> None:
        turn = call["turns"][i]
        path = None
        try:  # synthesised before the console is told, so its audio request finds the clip ready
            path = await voice.synthesize(turn["text"], call["voices"][turn["who"]])
        except Exception:  # noqa: BLE001 - no text to speech: the line is paced by the words
            pass
        await self.e.broadcast({"type": "live_turn", "id": call["id"], "i": i, "turn": turn, "speaking": True})
        if line := self.lines.get(call["id"]):
            await line.play(path, turn["who"], turn["text"], listen=False)

    async def _hear_live(self, call: dict, i: int) -> None:
        """Play one caller (or call-taker) utterance on the line and keep what the realtime model heard."""
        turn, lang = call["turns"][i], call["language"]
        path = config.ROOT / turn["audio"] if turn.get("audio") else None
        if path is None:
            try:
                path = await voice.synthesize(turn["text"], call["voices"][turn["who"]])
                turn["audio"] = path.relative_to(config.ROOT).as_posix()
            except Exception:  # noqa: BLE001
                path = None
        call["_hearing"] = i
        await self.e.broadcast({"type": "live_turn", "id": call["id"], "i": i, "turn": {**turn, "text": ""},
                                "listening": True})
        line = self.lines.get(call["id"])
        heard, model = (await line.play(path, turn["who"], turn["text"])) if line else (turn["text"], turn["model"])
        if model.startswith("mock") and path is not None and lang not in REALTIME_LANGS:
            # Voice Transcribe has no Sinhala: Spark listens to the utterance once it has been said.
            try:
                if said := await asyncio.to_thread(self.e.client.spark_listen, path, self.lang_name.get(lang, lang)):
                    heard, model = said, "Muse Spark"
            except Exception:  # noqa: BLE001
                pass
        if not model.startswith("mock"):
            self.e._count(model.replace(" (realtime)", ""))
            base = turn["model"]  # a recording is simply heard; a simulated caller or a call-taker keeps who spoke
            turn["model"] = model if not base or base.startswith("mock") else f"{base} · {model}"
        if turn["who"] == "taker":
            turn["heard"] = heard  # the call-taker's words are known; keep them, note what the line heard
        else:
            turn["text"] = heard
        call.pop("_hearing", None)
        await self.e.broadcast({"type": "live_turn", "id": call["id"], "i": i, "turn": turn})

    async def say(self, call: dict, act: str, en_kw: dict | None = None, keep: tuple[str, ...] = (), **kw) -> None:
        """Speak one act: the template, reworded by Spark when allowed and when every fact survives."""
        draft = self.loc["agent"][call["language"]][act].format(**kw)
        text, model, dropped = draft, "Agent", []
        if call.get("spark") and act not in FIXED:
            text, model, dropped = await self._spark(call, act, draft, keep)
        turn = {"who": "agent", "act": act, "model": model, "en": self.loc["agent"]["en"][act].format(**(en_kw or kw)),
                "text": text}
        if dropped:
            turn["rejected"] = dropped
        call["turns"].append(turn)
        call["acts"].append(act)
        if call.get("live"):
            await self._speak_live(call, len(call["turns"]) - 1)

    async def _spark(self, call: dict, act: str, draft: str, keep: tuple[str, ...]) -> tuple[str, str, list[str]]:
        crew = call["line"] == "radio"
        system = SPEAK_SYSTEM.format(desk="control room" if crew else "outage desk", line=call["line"],
                                     language=self.lang_name.get(call["language"], "English"),
                                     person="control-room operator" if crew else "call-centre agent")
        try:
            out = await asyncio.to_thread(self.e.client.spark_text, system,
                                          f"Purpose: {PURPOSE.get(act, act.replace('_', ' '))}.\nDraft: {draft}")
        except Exception:  # noqa: BLE001
            out = None
        if not out:
            return draft, "mock (template)", []
        self.e._count("Muse Spark")
        if dropped := facts_kept(draft, out, keep):
            return draft, "Code (Spark line failed fact check)", dropped
        return out.strip(), "Muse Spark", []

    async def hear(self, call: dict, text: str, model: str, audio: str | None = None, who: str = "caller") -> str:
        """Record what the caller (or crew) said; on a live call, play it on the line and return what was heard."""
        call["turns"].append({"who": who, "text": text, "model": model, "audio": audio})
        if call.get("live"):
            await self._hear_live(call, len(call["turns"]) - 1)
        return call["turns"][-1]["text"]

    @staticmethod
    def gloss(call: dict, fields: dict) -> None:
        """Show Spark's English summary under the caller's or crew's first words (live mode; mock has none)."""
        first = next((t for t in call["turns"] if t["who"] != "agent"), None)
        en = fields.get("summary_en") or ""
        if first and en and not en.startswith((first["text"], "[")):  # mock mode echoes the text: no gloss
            first["en"] = en

    def address(self, house, street) -> str:
        return self.loc["address"].format(house=house, street=street) if house else street

    # ---- during the call, before the report is filed --------------------------------------

    async def questions(self, call: dict, e: dict, fields: dict, loc: dict) -> str | None:
        """Confirm or ask for the address, and ask about hazards. Returns what the caller added, if anything."""
        eng, sim = self.e, self.e.sim
        key = loc.get("account") or e.get("from") or e["id"]
        if sim is None or e.get("followup") or key in eng.seen:
            return None  # a repeat or follow-up caller only needs the status
        said = []
        if loc.get("method") == "caller ID":
            await self.say(call, "confirm_address", address=self.address(loc.get("house_no"), loc.get("street")),
                           keep=(loc.get("street"),))
            await self.hear(call, sim.answer(e, "yes"), "Simulated caller")
        elif not loc.get("transformer"):
            await self.say(call, "ask_address")
            said.append(await self.hear(call, sim.answer(e, "address"), "Simulated caller"))
        if fields["hazard"] == "none":
            if known := self._hazard_known(loc):
                # Earlier callers already reported it: warn this one instead of asking.
                await self.say(call, "known_hazard", what=HAZARD_NAMES[call["language"]][known],
                               en_kw={"what": HAZARD_NAMES["en"][known]})
            elif e.get("audio") or not eng.pack.get("quiet_messages"):  # in a surge, keep unvoiced calls short
                await self.say(call, "ask_hazard")
                said.append(await self.hear(call, sim.answer(e, "hazard"), "Simulated caller"))
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
        if not call.get("live"):  # a live call already played the recording
            await self.hear(call, "…", model, e.get("audio"))
        else:
            call["turns"][-1]["text"] = "…"
        await self.say(call, "sms_fallback", code=self.loc["sms_label"].split()[0])
        await self.say(call, "close")
        if call.get("live"):
            await self.end_live(call)
        await self.e.log("Agent", f"{e['id']}: call not understood ({self.lang_name.get(e.get('language'), '?')})",
                         "asked the caller to send the breakdown SMS instead", e["id"])
        await self.e.broadcast({"type": "call", "id": e["id"], "call": call})
        if self.e.sim:
            self.e.sim.sms_fallback(e, self.e.elapsed)

    # ---- crew reports by phone or radio: read back what was understood before acting on it ------

    def crew_voice(self, e: dict) -> str:
        crews = self.loc["voices"]["crew"]
        crews = crews.get(e.get("language"), crews["en"])
        return e.get("voice") or crews[sum(map(ord, e.get("crew") or "")) % len(crews)]

    def crew_start(self, e: dict, text: str, model: str) -> dict:
        lang = self._lang(e.get("language"))
        call = {"language": lang, "turns": [], "acts": [], "escalated": False, "crew": e.get("crew"),
                "line": "radio", "spark": True,
                "voices": {"agent": self.loc["voices"]["agent"][lang], "crew": self.crew_voice(e)}}
        call["turns"].append({"who": "crew", "text": text, "model": model, "audio": e.get("audio")})
        return call

    async def crew_by_text(self, call: dict, e: dict) -> None:
        """No model could make out the crew's call: they send the report as a text message instead."""
        await self.say(call, "crew_text")
        await self.hear(call, e["text"], "Text message", who="crew")

    async def readback(self, call: dict, e: dict, ext, read: Callable[[str], Awaitable]):
        """Say back what Spark understood; act only on what the crew confirms (one correction allowed)."""
        for _ in range(2):
            f = ext.fields
            await self.say(call, "readback", summary=crew_summary(f, call["language"]),
                           en_kw={"summary": crew_summary(f, "en")}, keep=(f.get("street"),))
            if self.e.sim is None:
                return ext
            ok, reply = self.e.sim.readback(e, f)
            await self.hear(call, reply, "Simulated crew", who="crew")
            if ok:
                return ext
            ext = await read(" ".join(t["text"] for t in call["turns"] if t["who"] == "crew"))
        return ext

    async def crew_ack(self, call: dict, inc: dict | None, changed: bool) -> None:
        if inc and changed:
            await self.say(call, "crew_changed", kind=self.kind_title[inc["kind"]].lower())
        elif inc:
            await self.say(call, "crew_logged", incident=inc["id"], keep=(inc["id"],))
        else:
            await self.say(call, "crew_unmatched")

    # ---- after the report is filed: safety, a question for the tracer, status ---------------

    async def finish(self, msg: dict) -> None:
        eng, call, f = self.e, msg["call"], msg["fields"]
        loc = msg.get("location") or {}
        if msg["status"] == "junk":
            await self.say(call, "junk")
        else:
            if msg["status"] == "duplicate":
                first = next((m for m in eng.messages if m["id"] == msg.get("dup_of")), None)
                if first:
                    await self.say(call, "repeat", at=eng.clock(first["t"]))
            hazard = f.get("hazard")
            if hazard in SAFETY:
                await self.say(call, SAFETY[hazard])
            if urgent := self.urgent(f, loc):
                call["escalated"] = True
                await self.say(call, "escalate")
                await eng.log("Agent", f"{msg['id']}: urgent call flagged to the control room", urgent, msg["id"])
            if msg["status"] != "duplicate" and not msg.get("followup") and eng.sim:
                await self._neighbour(msg)
            await self._status(msg)
        await self.say(call, "close")
        if call.get("live"):
            await self.end_live(call)
        await eng.broadcast({"type": "call", "id": msg["id"], "call": call, "incident": msg.get("incident")})
        await eng.note("Agent", f"{msg['id']}: call answered ({self.lang_name.get(msg['language'], msg['language'])})",
                       " → ".join(a.replace("_", " ") for a in call["acts"]), msg["id"])

    def urgent(self, f: dict, loc: dict | None) -> str | None:
        """Why a call needs the control room's attention now (live wire, fire, critical customer), if it does."""
        hazard = f.get("hazard")
        if hazard in ESCALATE:
            return hazard.replace("_", " ") + " reported"
        customer = self.e.db.by_account(loc["account"]) if loc and loc.get("account") else None
        return f"critical customer ({customer.critical})" if customer and customer.critical else None

    async def transfer(self, call: dict, e: dict, why: str) -> None:
        """Put a live call through to a human call-taker (the copilot takes it from here); the line stays open."""
        call["escalated"] = call["taker"] = True
        await self.say(call, "transfer")
        await self.e.log("Agent", f"{e['id']}: call put through to a call-taker", why, e["id"])

    async def _status(self, msg: dict) -> None:
        act, kw = self.status_line(msg.get("location") or {}, msg.get("incident"))
        await self.say(msg["call"], act, **kw)

    def status_line(self, loc: dict, incident: str | None = None) -> tuple[str, dict]:
        """What to tell a caller about their outage: the act and its facts."""
        eng = self.e
        xf, acct = loc.get("transformer"), loc.get("account")
        inc = next((i for i in eng._active() if i["id"] == incident or (xf and xf in i["out"])
                    or (acct and acct in i["dead_customers"])), None)
        if inc:
            act = "status_" + CREW_STATE.get(inc["status"], "waiting")
            kind = "cause still being checked" if inc["kind"] == "unknown" else self.kind_title[inc["kind"]].lower()
            kw = {"kind": kind, "eta": eng.clock(inc["eta"]) if inc["eta"] else "–"}
        elif xf in eng.restored_at:
            act, kw = "status_restored_dark", {"at": eng.clock(eng.restored_at[xf])}
        else:
            act, kw = "status_locating", {}
        return act, kw

    async def _neighbour(self, msg: dict) -> None:
        """If the tracer is torn between two explanations that differ next door, ask the caller about next door."""
        call = msg["call"]
        if (q := self.neighbour_target((msg.get("location") or {}).get("transformer"))) is None:
            return
        L, target, who = q
        address = self.address(who.house_no, who.street)
        await self.say(call, "ask_neighbour", address=address, keep=(who.street,))
        answer, on = self.e.sim.neighbour(msg["event"], who)
        await self.hear(call, answer, "Simulated caller")
        await self.neighbour_answer(msg["id"], msg["language"], msg.get("from"), L, target, who,
                                    call["turns"][-2]["text"], call["turns"][-1]["text"], on)

    def neighbour_target(self, xf: str | None):
        """(located fault, transformer next door, a customer there) when next door would separate two explanations."""
        from .engine import ASK_BELOW, PROBE_GAP_S

        eng = self.e
        if not xf:
            return None
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
            return L, target, who
        return None

    async def neighbour_answer(self, via: str, lang: str, frm: str | None, L, target: str, who, question: str,
                               answer: str, on: bool) -> None:
        """The caller's answer about next door becomes a probe reply: evidence like any SMS answer, then a re-trace."""
        eng, c, alt = self.e, L.candidate, L.alternative
        probe = {"id": f"Q{len(eng.probes) + 1}", "t": round(eng.elapsed), "fault": c.id, "rival": alt.id,
                 "transformer": target, "to": frm, "name": who.name, "street": who.street,
                 "house_no": who.house_no, "language": lang, "text": question,
                 "answer": None, "lat": who.lat, "lon": who.lon, "via": via}
        eng.probes.append(probe)
        await eng.log("Agent", f"Asked caller {via} about {self.address(who.house_no, who.street)} "
                      f"(transformer {target})",
                      f"{c.id} {L.confidence:.0%} vs {alt.id} {L.alt_confidence:.0%}: next door separates the two",
                      probe["id"])
        await eng.broadcast({"type": "probe", "probe": probe})
        # The answer is read like any other message (Spark, or its label in mock mode) and becomes evidence.
        await eng._complaint({"t": eng.elapsed, "type": "complaint", "id": f"{via}-{probe['id']}",
                              "channel": "call", "language": lang, "text": answer, "probe_reply": probe["id"],
                              "truth": {"street": who.street, "house_no": who.house_no, "hazard": "none",
                                        "symptom": "power_on" if on else "no_power"}})
        await eng.recompute()
