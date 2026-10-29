"""The triage loop.

Each incoming event becomes evidence. The tracer locates faults from the evidence no
open incident has claimed yet; once a fault is located with enough confidence it
becomes an incident that owns its complaints, lockouts and damage reports. Incidents
then run their lifecycle on the storm clock: crews are dispatched by priority, travel,
report what they find (which can change the diagnosis), repair, and power is restored.
Complaints that keep coming from a restored area are unclaimed again, so the tracer
finds whatever fault was hiding behind the first one.

Restoration switching is offered per incident and checked for safety; the operator
approves it. Every step is logged to a timeline tagged with the model (or code) that
did it.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Any, Awaitable, Callable

import httpx

from . import config
from .extract import Extraction, Extractor
from . import packs
from .grid import haversine_m
from .models import ModelClient
from .network import NetworkState, live_transformers, restoration_plans
from .planner import STEPS, Crew, Job, schedule, score
from .tracer import Damage, Evidence, Tracer
from .vision import analyse_photo

LOCATED_AT = 0.8  # confidence at which a suspected fault becomes an incident
ASK_BELOW = 0.85  # confidence below which the agent asks a customer to disambiguate
PROBE_GAP_S = 120
SPEED_KMH = 25
ROAD_FACTOR = 1.3
REVIEW_FIELDS = ["street", "house_no", "symptom", "hazard", "is_junk"]
SECTION_KINDS = {"pole_down", "tree_on_line", "live_wire", "wire_down"}
LANG_NAME = {"en": "English", "si": "Sinhala", "ta": "Tamil", "es": "Spanish", "hi": "Hindi"}
KIND_TITLE = {"pole_down": "Pole down", "tree_on_line": "Tree on line", "live_wire": "Live wire on road",
              "wire_down": "Wire down", "blown_fuse": "Blown fuse", "service_wire": "Service wire down",
              "unknown": "Outage, cause unknown"}

EXPLAIN_SYSTEM = """You are the reasoning voice of GridMedic, an outage-triage agent for a distribution utility.
Given the facts the fault tracer used, explain to the control-room dispatcher in at most two short
sentences why this fault is located where it is and what to send. Plain language, no hedging, no lists."""
NOTICE_SYSTEM = """Write a short SMS from an electricity utility's outage desk to a customer, in the requested
language and script. Say the fault affecting them has been found, a crew is assigned, and give the
estimated restoration time exactly as provided. One or two sentences, polite, no emojis."""

Broadcast = Callable[[dict], Awaitable[None]]


def clock_str(t: float, start_hour: int = 15) -> str:
    m = int(start_hour * 60 + t // 60)
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


class Engine:
    def __init__(self, scenario: dict, broadcast: Broadcast) -> None:
        self.feeder, self.db = packs.network(scenario)
        self.pack, self.loc = packs.pack(scenario), packs.locale(scenario)
        self.sms_code = re.compile(self.loc["sms_code"], re.I)
        self.sms_model = f"Code ({self.loc['sms_label']}, no AI)"
        self.client = ModelClient()
        # Muse Glimmer served locally (vLLM / llama.cpp, OpenAI-compatible); always "live" because it is local.
        self.extractor = Extractor(self.client, hint=self.loc["hint"])
        self.glimmer = Extractor(ModelClient(mode="live"), model=config.GLIMMER_MODEL, base=config.GLIMMER_BASE,
                                 label="Muse Glimmer (offline)", hint=self.loc["hint"])
        self.customers = self.db.counts_by_transformer()
        self.tracer = Tracer(self.feeder, self.customers)
        self.critical = self.db.critical_by_transformer()
        self.scenario = scenario
        self.broadcast = broadcast
        self.sim = None  # the simulated world (Replayer): answers questions, plays crews and customers
        self.reset()

    def clock(self, t: float) -> str:
        return clock_str(t, self.pack["start_hour"])

    def reset(self) -> None:
        self.elapsed = 0.0
        self._last_trace = -1e9
        self._dirty = False
        self.cmi = 0.0
        self._out_now = 0
        self._quiet: Counter = Counter()
        self.offline = False
        self.queued: list[dict] = []
        self.messages: list[dict] = []
        self.timeline: list[dict] = []
        self.field_damage: list[Damage] = []
        self.damage_owner: dict[int, str] = {}  # id(Damage) -> incident id
        self.config_open: set[str] = set(self.feeder.normally_open)  # device states the control room knows
        self.scada_owner: dict[str, str] = {}  # locked-out device -> incident id
        self.probes: list[dict] = []
        self.notices: list[dict] = []
        self.incidents: list[dict] = []
        self.suspects: list[dict] = []
        self.hazards: list[dict] = []
        self.restored_at: dict[str, float] = {}
        self.plan: dict = {}
        self.baseline: dict = {}
        self.model_calls: Counter = Counter()
        meters = self.pack.get("smart_meters")
        self.ami: list[tuple[float, str, str]] = []  # (time, account, transformer) last gasps
        self.ami_ok = bool(meters)
        self.meter_cov = meters["coverage"] if meters else 0.0
        self.crews = {c["id"]: {"id": c["id"], "name": c["name"], "skills": set(c["skills"]), "base": c["base"],
                                "lat": self.feeder.bus_pos[c["base"]][0], "lon": self.feeder.bus_pos[c["base"]][1],
                                "status": "idle", "incident": None, "step": None}
                      for c in self.scenario["crews"]}
        self._rebuild()

    # ---- helpers ------------------------------------------------------------

    def _count(self, model: str) -> None:
        if not model.startswith(("Code", "SCADA", "Agent", "mock", "Network", "Crew", "Operator", "Smart")):
            for m in model.split(" + "):
                self.model_calls[m] += 1

    async def note(self, model: str, title: str, detail: str = "", ref: str | None = None) -> None:
        """Per-message log line; in quiet (high-volume) scenarios only counted, then summarised."""
        if self.pack.get("quiet_messages"):
            self._count(model)
            self._quiet[title.split(": ", 1)[-1].split(" ->")[0].split(" (")[0]] += 1
            return
        await self.log(model, title, detail, ref)

    async def log(self, model: str, title: str, detail: str = "", ref: str | None = None) -> None:
        entry = {"t": round(self.elapsed), "clock": self.clock(self.elapsed), "model": model, "title": title,
                 "detail": detail, "ref": ref}
        self.timeline.append(entry)
        self._count(model)
        await self.broadcast({"type": "timeline", "entry": entry})

    def _locate(self, fields: dict, sender: str | None) -> dict:
        """Place a message on the grid: account, then address, then caller ID, then landmark."""
        c = None
        method = None
        if fields.get("account_no"):
            c, method = self.db.by_account(fields["account_no"]), "account number"
        if c is None and fields.get("street") and fields.get("house_no"):
            c, s = self.db.by_address(fields["street"], fields["house_no"])
            method = f"address match ({s:.0%})" if c else None
        if c is None and sender:
            c, method = self.db.by_phone(sender), "caller ID"
            if c and fields.get("street"):
                street, _ = self.db.match_street(fields["street"])
                if street and street != c.street:
                    c, method = None, None  # calling about somewhere else
        if c:
            return {"account": c.account_no, "name": c.name, "transformer": c.transformer_id,
                    "lat": c.lat, "lon": c.lon, "method": method, "street": c.street, "house_no": c.house_no}
        lm = self.db.match_landmark(" ".join(filter(None, [fields.get("landmark"), fields.get("street")])))
        if lm:
            return {"account": None, "transformer": lm["transformer_id"], "lat": lm["lat"], "lon": lm["lon"],
                    "method": f"landmark: {lm['name']}"}
        if fields.get("street"):
            street, s = self.db.match_street(fields["street"])
            if street and s > 0.6:
                xf = [t for t in self.feeder.transformers.values()
                      if self.feeder.sections[t.section].street == street]
                if xf:
                    t = xf[len(xf) // 2]
                    return {"account": None, "transformer": None, "lat": t.lat, "lon": t.lon,
                            "method": f"street only: {street}", "street_xf": t.id}
        return {"account": None, "transformer": None, "lat": None, "lon": None, "method": "not located"}

    def _damage(self, source: str, kind: str, loc: dict, strength: float) -> Damage | None:
        xf = loc.get("transformer") or loc.get("street_xf")
        if not xf or kind in ("none", "other"):
            return None
        t = self.feeder.transformers[xf]
        return Damage(source, kind, t.section, xf, strength, loc["lat"], loc["lon"])

    def _hazard(self, msg_id: str, kind: str, loc: dict, text: str, t: float) -> dict | None:
        if kind not in ("live_wire", "wire_down", "pole_down", "fire") or loc.get("lat") is None:
            return None
        for h in self.hazards:
            if h["kind"] == kind and haversine_m((h["lat"], h["lon"]), (loc["lat"], loc["lon"])) < 250:
                h["evidence"].append(msg_id)
                return h
        h = {"id": f"H{len(self.hazards) + 1}", "kind": kind, "lat": loc["lat"], "lon": loc["lon"],
             "evidence": [msg_id], "first_t": round(t), "text": text, "safe": False}
        self.hazards.append(h)
        return h

    def _incident(self, iid: str | None) -> dict | None:
        return next((i for i in self.incidents if i["id"] == iid), None)

    def _active(self) -> list[dict]:
        return [i for i in self.incidents if i["status"] != "restored"]

    # ---- network belief ------------------------------------------------------------

    def belief(self, without: dict | None = None) -> NetworkState:
        """What the control room believes about the network: known device states plus every open incident."""
        st = NetworkState(open=set(self.config_open))
        for inc in self._active():
            if inc is without:
                # As if this fault had never happened: its device closed and its switching undone.
                for op, dev in inc["switching"]:
                    (st.open.discard if op == "open" else st.open.add)(dev)
                st.open -= set(inc["devices"])
                continue
            st.open |= {d for d in inc["devices"] if self.feeder.devices[d].kind == "fuse"}
            if inc["site_section"] and (inc["kind"] in SECTION_KINDS or inc["cand"].startswith("LINE-")):
                st.faulted.add(inc["site_section"])
            elif not inc["site_xf"] and not inc["dead_customers"]:
                st.suspect |= set(inc["zone"])  # somewhere in this zone, not pinned down yet
            if inc["kind"] == "blown_fuse" and inc["site_xf"]:
                st.dead_transformers.add(inc["site_xf"])
            st.dead_customers |= set(inc["dead_customers"])
        return st

    def _refresh_outages(self) -> None:
        live = live_transformers(self.feeder, self.belief())
        for inc in self._active():
            alone = live_transformers(self.feeder, self.belief(without=inc))
            inc["out"] = sorted(alone - live)
            inc["customers_out"] = sum(self.customers.get(t, 0) for t in inc["out"]) + len(inc["dead_customers"])
            inc["critical"] = [x for t in inc["out"] for x in self.critical.get(t, [])]
        self._out_now = sum(i["customers_out"] for i in self._active())

    def _tick_cmi(self, t: float) -> None:
        """Customer minutes interrupted (as GridMedic sees the outage), the utility's standard measure."""
        self.cmi += self._out_now * max(t - self.elapsed, 0) / 60

    def work_zones(self) -> dict[str, str]:
        zones = {}
        for c in self.crews.values():
            inc = self._incident(c["incident"])
            if c["status"] == "onsite" and inc and inc["site_section"]:
                zones[inc["site_section"]] = c["name"]
        return zones

    # ---- evidence: rebuilt from the messages no incident has claimed ----------------------

    def _rebuild(self) -> None:
        safe = {h["id"] for h in self.hazards if h.get("safe")}
        self.ev = Evidence(scada_open={d for d in self.config_open if d in self.feeder.devices
                                       and d not in self.scada_owner},
                           damage=[d for d in self.field_damage if id(d) not in self.damage_owner])
        self.seen: dict[str, str] = {}
        self.hazards = []
        self.languages: dict[str, str] = {}
        for m in self.messages:
            self._apply(m)
        if self.meter_cov:
            self.ev.meter_counts = {t: round(n * self.meter_cov) for t, n in self.customers.items()}
            # A silent meter only means "power on" once last-gasp traffic has settled for a minute.
            self.ev.ami_ok = self.ami_ok and self.elapsed - max((t for t, _, _ in self.ami), default=-999) >= 60
            claimed = {t for i in self._active() for t in i["out"]}
            for t, acct, xf in self.ami:
                if xf not in claimed and self.restored_at.get(xf, -1) < t:
                    self.ev.meters.setdefault(xf, set()).add(acct)
        for h in self.hazards:
            h["safe"] = h["id"] in safe

    def _apply(self, m: dict) -> None:
        """Turn one message into evidence (dedup, reports, probes, hazards, damage) unless an incident owns it."""
        f, loc = m["fields"], m.get("location") or {}
        owned = m.get("incident") is not None
        if m["channel"] == "crew":
            if not owned and (d := self._damage(m["id"], f["damage"], loc, 4.0)):
                self.ev.damage.append(d)
            if f.get("energised"):
                self._hazard(m["id"], "live_wire", loc, f["summary_en"], m["t"])
            return
        if f.get("is_junk"):
            m["status"] = "junk"
            return
        key = loc.get("account") or m.get("from") or m["id"]
        if key in self.seen and self.seen[key] != m["id"] and not m.get("probe_reply") and not m.get("followup"):
            m["status"], m["dup_of"] = "duplicate", self.seen[key]
            return
        if m.get("followup") or key not in self.seen:
            self.seen[key] = m["id"]
        m["status"] = "new"
        if f["hazard"] != "none":
            self._hazard(m["id"], f["hazard"], loc, f.get("summary_en", ""), m["t"])
        if owned:
            return
        xf = loc.get("transformer")
        if m.get("probe_reply") and xf:
            self.ev.probes[xf] = f["symptom"] == "power_on"
        elif xf and f["symptom"] in ("no_power", "partial_power", "flicker"):
            self.ev.reports.setdefault(xf, set()).add(key)
            self.ev.report_ids.setdefault(xf, []).append(m["id"])
            if f["symptom"] != "no_power":
                self.ev.partial.setdefault(xf, set()).add(key)
            self.languages[xf] = m["language"]
        if f["hazard"] != "none" and (d := self._damage(m["id"], f["hazard"], loc, 1.5)):
            self.ev.damage.append(d)

    def _claim(self, m: dict) -> None:
        """Give a new message to the open incident whose outage it belongs to, if any."""
        loc = m.get("location") or {}
        xf, acct = loc.get("transformer"), loc.get("account")
        for inc in self._active():
            if (xf and xf in inc["out"]) or (acct and acct in inc["dead_customers"]):
                m["incident"] = inc["id"]
                inc["reports"].append(m["id"])
                return

    # ---- event handlers -------------------------------------------------------

    async def handle(self, event: dict) -> None:
        await self.advance(event["t"])
        kind = event["type"]
        if kind == "scada":
            await self._scada(event)
        elif kind == "complaint":
            if self.offline and event["channel"] == "call":
                self.queued.append(event)
                await self.log("Network", f"{event['id']}: call recorded, queued for transcription",
                               "Voice Transcribe is a cloud model; the network is down", event["id"])
                return
            await self._complaint(event)
        elif kind == "crew_note":
            await self._crew_note(event)
        elif kind == "drone":
            await self._drone(event)
        elif kind == "ami":
            await self._ami(event)
        elif kind == "ami_status":
            self.ami_ok = event["ok"]
            await self.log("Smart meters", "Meter network down" if not event["ok"] else "Meter network back",
                           (event.get("detail", "") + "; locating from complaints and field reports only")
                           if not event["ok"] else "")
        urgent = kind in ("scada", "crew_note", "ami_status") or event.get("probe_reply") or event.get("channel") == "web"
        if urgent or self.elapsed - self._last_trace >= self.pack.get("retrace_s", 0):
            await self.recompute()
        else:
            self._dirty = True

    async def _ami(self, e: dict) -> None:
        xfs = Counter()
        for acct in e["accounts"]:
            if c := self.db.by_account(acct):
                self.ami.append((e["t"], acct, c.transformer_id))
                xfs[c.transformer_id] += 1
        await self.log("Smart meters", f"{len(e['accounts'])} last-gasp messages",
                       f"from {len(xfs)} transformers: " + ", ".join(f"{t} ({n})" for t, n in xfs.most_common(6)))

    async def _scada(self, e: dict) -> None:
        dev = self.feeder.devices[e["device"]]
        if e["event"] == "lockout":
            self.config_open.add(dev.id)
        await self.log("SCADA", f"{dev.label} ({dev.id}): {e['event']}",
                       "locked out, needs a crew" if e["event"] == "lockout" else "")
        await self.broadcast({"type": "scada", "device": dev.id, "event": e["event"], "t": e["t"]})

    async def _transcript(self, e: dict) -> str:
        audio = e.get("audio")
        if audio and (config.ROOT / audio).exists():
            bias = {"en": ["English"], "ta": ["Tamil", "English"], "si": ["English"]}.get(e.get("language"))
            try:
                res = await asyncio.to_thread(self.client.transcribe, config.ROOT / audio, bias)
            except Exception as err:  # noqa: BLE001
                res = None
                await self.log("Code", f"{e['id']}: transcription failed, using text", str(err)[:160], e["id"])
            if res:
                await self.log("Voice Transcribe", f"{e['id']}: call transcribed", res["transcript"][:160], e["id"])
                return res["transcript"]
        return e["text"]

    async def _extract(self, text: str, e: dict) -> Extraction:
        if m := self.sms_code.match(text):
            # The utility's breakdown SMS code needs no model at all.
            return Extraction({"language": "en", "account_no": m.group(1), "street": None, "house_no": None,
                               "landmark": None, "symptom": "no_power", "hazard": "none", "cause_hint": None,
                               "is_junk": False, "summary_en": f"Breakdown SMS for account {m.group(1)}"},
                              self.sms_model)
        ex = self.glimmer if self.offline else self.extractor
        out = await asyncio.to_thread(ex.complaint, text, e.get("truth", {}), e.get("language", "en"))
        if out.mock and self.offline:
            out.model = "mock (Glimmer not running)"
        return out

    async def _complaint(self, e: dict) -> None:
        text = (await self._transcript(e)) if e["channel"] == "call" else e["text"]
        ext = await self._extract(text, e)
        f = ext.fields
        msg = {"id": e["id"], "t": e["t"], "channel": e["channel"], "language": f.get("language") or e.get("language"),
               "from": e.get("from"), "text": text, "fields": f, "model": ext.model, "photo": e.get("photo"),
               "probe_reply": e.get("probe_reply"), "followup": e.get("followup"), "event": e}
        await (self.log if f["hazard"] != "none" else self.note)(ext.model, f"{e['id']}: {f['symptom'].replace('_', ' ')}"
                       + (f", hazard {f['hazard'].replace('_', ' ')}" if f["hazard"] != "none" else "")
                       + (" (junk)" if f["is_junk"] else ""), f.get("summary_en", "")[:160], e["id"])
        if not f["is_junk"]:
            msg["location"] = self._locate(f, e.get("from"))
            if not e.get("probe_reply"):
                self._claim(msg)
        n_hazards = len(self.hazards)
        self.messages.append(msg)
        self._apply(msg)
        loc = msg.get("location") or {}
        if msg["status"] == "duplicate":
            await self.note("Code", f"{e['id']}: duplicate of {msg['dup_of']}",
                           f"same {'account' if loc.get('account') else 'sender'}", e["id"])
        elif msg["status"] == "new":
            xf = loc.get("transformer")
            owner = f" -> {msg['incident']}" if msg.get("incident") else ""
            await self.note("Code", f"{e['id']}: located by {loc['method']}{owner}",
                           f"{loc.get('street', '')} {loc.get('house_no') or ''} -> transformer {xf}" if xf else "",
                           e["id"])
            if xf and xf in self.restored_at and not msg.get("incident") and f["symptom"] == "no_power":
                await self.log("Agent", f"{e['id']}: still dark after restoration",
                               f"transformer {xf} was restored at {self.clock(self.restored_at[xf])}; "
                               "looking for a second fault", e["id"])
            if e.get("probe_reply") and xf:
                on = f["symptom"] == "power_on"
                for p in self.probes:
                    if p["id"] == e["probe_reply"]:
                        p["answer"], p["answered_t"] = ("power ON" if on else "power OFF"), e["t"]
                await self.log("Agent", f"Answer from {xf}: power is {'ON' if on else 'OFF'}",
                               "rules out the wider outage" if on else "the outage extends here", e["id"])
        if len(self.hazards) > n_hazards:
            h = self.hazards[-1]
            await self.log("Code", f"Hazard {h['id']}: {h['kind'].replace('_', ' ')} reported",
                           "public safety, ranked above every outage", e["id"])
        await self.broadcast({"type": "message", "message": _public(msg)})
        if e.get("photo") and msg["status"] != "junk":
            await self._photo(e["id"], e["photo"], loc, f["hazard"], 2.5, msg.get("incident"))

    async def _photo(self, ref: str, path: str, loc: dict, truth_damage: str, strength: float,
                     owner: str | None = None) -> None:
        try:
            res = await asyncio.to_thread(analyse_photo, self.client, path, truth_damage)
        except Exception as err:  # noqa: BLE001
            await self.log("Code", f"{ref}: photo analysis failed", str(err)[:160], ref)
            return
        detail = res["description"]
        if res.get("clearance_m") is not None:
            detail += f" | wire clearance ~{res['clearance_m']} m"
        await self.log(" + ".join(res["models"]), f"{ref}: photo shows {res['damage'].replace('_', ' ')}", detail, ref)
        if d := self._damage(ref + "/photo", res["damage"], loc, strength):
            self.field_damage.append(d)
            if owner:
                self.damage_owner[id(d)] = owner
                if inc := self._incident(owner):
                    inc["damage"].append(d)
        await self.broadcast({"type": "photo", "ref": ref, "path": path, "analysis": res, "lat": loc.get("lat"),
                              "lon": loc.get("lon")})

    async def _crew_note(self, e: dict) -> None:
        text = await self._transcript(e)
        ex = self.glimmer if self.offline else self.extractor
        ext = await asyncio.to_thread(ex.crew_note, text, e.get("truth", {}))
        f = ext.fields
        loc = self._locate(f, None)
        await self.log(ext.model, f"{e['id']} ({e['crew']}): {f['damage'].replace('_', ' ')}"
                       + (", device is fine" if f.get("device_ok") else ""), f["summary_en"][:200], e["id"])
        msg = {"id": e["id"], "t": e["t"], "channel": "crew", "language": e.get("language", "en"),
               "from": e["crew"], "text": text, "fields": f, "model": ext.model, "location": loc, "status": "crew",
               "event": e}
        inc = self._incident(e.get("incident"))
        if inc is None:
            # A patrol report: give it to the open incident whose area it falls in, if any.
            xf = loc.get("transformer")
            inc = next((i for i in self._active() if xf and (xf in i["out"] or
                        self.feeder.transformers[xf].section in i["zone"])), None)
        if inc:
            msg["incident"] = inc["id"]
            if d := self._damage(e["id"], f["damage"], loc, 4.0):
                inc["damage"].append(d)
            await self._site_findings(inc, f, loc, e)
        self.messages.append(msg)
        self._apply(msg)
        await self.broadcast({"type": "message", "message": _public(msg)})
        if e.get("photo"):
            await self._photo(e["id"], e["photo"], loc, f["damage"], 3.0, msg.get("incident"))

    async def _drone(self, e: dict) -> None:
        truth = e.get("truth", {})
        loc = self._locate(truth, None)
        exists = (config.ROOT / e["file"]).exists()
        await self.log("SAM 3.1" if exists else "mock (ground truth)",
                       f"{e['id']}: drone clip shows {truth.get('damage', 'damage').replace('_', ' ')}",
                       e.get("caption", "") + ("" if exists else " (clip not added yet)"), e["id"])
        if d := self._damage(e["id"], truth.get("damage", "other"), loc, 3.0):
            self.field_damage.append(d)
            owner = next((i for i in self._active() if d.section in i["zone"] or d.transformer in i["out"]), None)
            if owner:
                self.damage_owner[id(d)] = owner["id"]
                owner["damage"].append(d)
        await self.broadcast({"type": "drone", "ref": e["id"], "path": e["file"], "lat": loc.get("lat"),
                              "lon": loc.get("lon"), "caption": e.get("caption")})

    async def _site_findings(self, inc: dict, f: dict, loc: dict, e: dict) -> None:
        """A crew's report about an incident: confirm it, or change the diagnosis."""
        damage = f["damage"]
        if damage in ("none", "other"):
            return
        old_title = inc["title"]
        before = f"{inc['title']} at {inc['label']} ({inc['confidence']:.0%})"
        if damage == "service_wire" and inc["site_xf"]:
            lo, hi = f.get("house_from"), f.get("house_to")
            street = loc.get("street") or self.db.match_street(f.get("street") or "")[0]
            custs = [c for c in self.db.customers_on(inc["site_xf"])
                     if lo is not None and hi is not None and lo <= c.house_no <= hi and c.street == street]
            inc.update(kind="service_wire", cand=f"SVC-{inc['site_xf']}", devices=[],
                       label=f"{street} {lo}-{hi}", dead_customers=[c.account_no for c in custs])
        else:
            inc["kind"] = "blown_fuse" if damage == "transformer_failure" else damage
        if damage in SECTION_KINDS and loc.get("transformer"):
            inc["site_section"] = self.feeder.transformers[loc["transformer"]].section
        if loc.get("lat"):
            inc["lat"], inc["lon"] = loc["lat"], loc["lon"]
        inc["title"] = KIND_TITLE[inc["kind"]]
        changed = bool(f.get("device_ok")) or (old_title != inc["title"] and old_title != KIND_TITLE["unknown"])
        inc["confidence"] = 0.97
        inc["confirmed_by"] = e.get("crew")
        if changed:
            after = f"{inc['title']} at {inc['label']} ({inc['confidence']:.0%})"
            inc["history"].append({"t": round(self.elapsed), "before": before, "after": after, "by": e.get("crew")})
            inc["mind_changed"] = True
            await self.log("Agent", f"Mind changed ↺ {inc['id']}",
                           f"{before} → {after}, from {e.get('crew')}'s report", inc["id"])
        self._refresh_outages()
        self._replan_steps(inc)

    # ---- network outage: Glimmer offline, Spark reconciles afterwards -------------

    async def set_offline(self, offline: bool) -> None:
        if offline == self.offline:
            return
        self.offline = offline
        if offline:
            try:
                httpx.get(f"{config.GLIMMER_BASE}/models", timeout=1.5).raise_for_status()
                self.glimmer.enabled = True
            except Exception:  # noqa: BLE001
                self.glimmer.enabled = False
            await self.log("Network", "Network down: switching to Muse Glimmer on this laptop",
                           "text messages keep flowing through the open-weights model; calls queue for transcription"
                           + ("" if self.glimmer.enabled else f" (no Glimmer server at {config.GLIMMER_BASE}: mock)"))
        else:
            await self.log("Network", "Network back: Muse Spark reviews the offline work",
                           f"{len(self.queued)} queued calls to transcribe")
            await self._reconcile()
            queued, self.queued = self.queued, []
            for e in queued:
                await self._complaint(e)
        await self.broadcast({"type": "network", "offline": offline})
        await self.recompute()

    async def _reconcile(self) -> None:
        reviewed = corrected = 0
        for m in self.messages:
            if not m["model"].startswith(("Muse Glimmer", "mock (Glimmer")) or m["channel"] == "crew":
                continue
            e = m["event"]
            ext = await asyncio.to_thread(self.extractor.complaint, m["text"], e.get("truth", {}), e.get("language", "en"))
            reviewed += 1
            diffs = [k for k in REVIEW_FIELDS if ext.fields.get(k) != m["fields"].get(k)]
            if diffs:
                corrected += 1
                await self.log(ext.model, f"{m['id']}: corrected offline extraction",
                               "; ".join(f"{k}: {m['fields'].get(k)} -> {ext.fields.get(k)}" for k in diffs), m["id"])
                m["fields"] = ext.fields
                if not ext.fields["is_junk"]:
                    m["location"] = self._locate(ext.fields, m.get("from"))
            m["model"] = f"{m['model']} ✓ {ext.model}"
        self._rebuild()
        await self.log("Code", f"Offline review: {reviewed} messages checked, {corrected} corrected",
                       "evidence rebuilt from the corrected record")
        await self.broadcast({"type": "messages", "messages": [_public(m) for m in self.messages]})

    # ---- locating: suspects become incidents ------------------------------------------

    def _fault_kind(self, damage: list[Damage], cand_kind: str) -> str:
        kinds = Counter(d.kind for d in damage)
        if kinds:
            if "live_wire" in kinds:
                return "live_wire"
            k = kinds.most_common(1)[0][0]
            return "blown_fuse" if k in ("transformer_bang", "transformer_failure") else k
        # A single transformer out on its own is most often its drop-out fuse.
        return "blown_fuse" if cand_kind == "xfmr_fuse" else "unknown"

    async def _merge_into(self, L) -> dict | None:
        """The same physical fault seen again: widen the open incident (e.g. the fuse above a break blew)."""
        c = L.candidate
        for inc in self._active():
            mine = set(inc["out"])
            if not mine or len(mine & c.out) < 0.5 * min(len(mine), len(c.out)):
                continue
            if c.out > mine and c.kind != "xfmr_fuse":
                inc.update(cand=c.id, label=c.label, zone=sorted(set(inc["zone"]) | c.zone),
                           devices=sorted(set(inc["devices"]) | ({c.id} if c.id in self.feeder.devices else set())))
                if c.id in self.config_open:
                    self.scada_owner[c.id] = inc["id"]
                await self.log("Code", f"{inc['id']} widened to {c.label}",
                               "more of the area is dark than the first explanation covered", inc["id"])
            for m in self.messages:
                xf = (m.get("location") or {}).get("transformer")
                if m.get("incident") is None and xf in c.out and m["channel"] != "crew" and not m.get("probe_reply"):
                    m["incident"] = inc["id"]
                    inc["reports"].append(m["id"])
            for d in L.damage:
                self.damage_owner[id(d)] = inc["id"]
            self._refresh_outages()
            return inc
        return None

    async def _open_incident(self, L) -> dict:
        if (merged := await self._merge_into(L)) is not None:
            return merged
        c = L.candidate
        iid = f"I{len(self.incidents) + 1}"
        kind = self._fault_kind(L.damage, c.kind)
        sections = Counter(d.section for d in L.damage if d.section in c.zone)
        site_section = sections.most_common(1)[0][0] if sections else (c.section if c.kind == "line" else None)
        lat, lon = (c.lat, c.lon)
        if L.damage:
            lat = sum(d.lat for d in L.damage) / len(L.damage)
            lon = sum(d.lon for d in L.damage) / len(L.damage)
        after_restore = any(t in self.restored_at for t in c.out if self.ev.reports.get(t))
        inc = {
            "id": iid, "cand": c.id, "kind": kind, "title": KIND_TITLE[kind], "label": c.label,
            "devices": [c.id] if c.id in self.feeder.devices else [], "zone": sorted(c.zone),
            "site_section": site_section, "site_xf": "T-" + c.id[3:] if c.kind == "xfmr_fuse" else None,
            "dead_customers": [], "lat": lat, "lon": lon, "confidence": round(L.confidence, 3),
            "alternative": {"id": L.alternative.id, "label": L.alternative.label,
                            "confidence": round(L.alt_confidence, 3)} if L.alternative else None,
            "reasons": L.reasons, "located_at": self.elapsed, "status": "located", "steps": [], "history": [],
            "reports": [], "damage": list(L.damage), "out": sorted(c.out), "customers_out": 0, "critical": [],
            "mind_changed": False, "after_restore": after_restore, "restored_at": None, "switching": [],
            "plans": [], "explanation": None, "explanation_model": None, "explained_kind": None, "notified": [],
            "first_t": self.elapsed, "priority": 0.0, "breakdown": {}, "eta": None,
        }
        if self.sim:
            inc["truth"] = self.sim.identify(self._info(inc))  # scoring only; the agent never reads it
        self.incidents.append(inc)
        # The incident claims its evidence: complaints on its transformers, its lockout, its damage.
        damage_msgs = {d.source.split("/")[0] for d in L.damage}
        for m in self.messages:
            xf = (m.get("location") or {}).get("transformer")
            if m.get("incident") is None and not m.get("probe_reply") and (
                    (xf in c.out and m["channel"] != "crew") or m["id"] in damage_msgs):
                m["incident"] = iid
                inc["reports"].append(m["id"])
        inc["first_t"] = min((m["t"] for m in self.messages if m["id"] in inc["reports"]), default=self.elapsed)
        if c.id in self.config_open:
            self.scada_owner[c.id] = iid
        for d in L.damage:
            self.damage_owner[id(d)] = iid
        self._refresh_outages()
        self._replan_steps(inc)
        await self.log("Code", f"Located {iid}: {c.label}" + (" (found after restoration)" if after_restore else ""),
                       f"{L.confidence:.0%} confident; " + "; ".join(L.reasons), iid)
        return inc

    def _replan_steps(self, inc: dict) -> None:
        """Work steps for the incident's current diagnosis, keeping work already done or under way."""
        done = [s for s in inc["steps"] if s["status"] == "done"]
        doing = [s for s in inc["steps"] if s["status"] in ("enroute", "onsite")]
        new = [{"skills": sorted(sk), "minutes": m, "task": label, "status": "pending", "crew": None}
               for sk, m, label in STEPS.get(inc["kind"], STEPS["unknown"])]
        new = [s for s in new if s["task"] not in {d["task"] for d in done}]
        if doing:
            cur = doing[0]
            crew = self.crews[cur["crew"]]
            if new and set(new[0]["skills"]) <= crew["skills"]:
                # The crew already assigned carries on with the (possibly new) first task.
                keep = {k: cur[k] for k in ("status", "crew", "arrive_t", "depart_t", "from_") if k in cur}
                new[0].update(keep)
                start = self.elapsed if cur["status"] == "onsite" else cur["arrive_t"]
                new[0]["end_t"] = start + new[0]["minutes"] * 60
                crew["step"] = new[0]["task"]
            else:
                # This crew cannot do the repair: its visit counts as the patrol, and it is released.
                cur.update(status="done", end_t=self.elapsed, task=f"{cur['task']} (released)")
                done.append(cur)
                crew.update(status="idle", incident=None, step=None)
        inc["steps"] = done + new

    async def recompute(self) -> None:
        self._last_trace, self._dirty = self.elapsed, False
        if self._quiet:
            q, self._quiet = self._quiet, Counter()
            await self.log("Code", f"Processed {sum(v for k, v in q.items() if k.startswith(('no power', 'partial', 'flicker', 'none', 'power on')))} messages",
                           ", ".join(f"{k}: {v}" for k, v in q.most_common(6)))
        self._rebuild()
        located = self.tracer.locate(self.ev, self.elapsed)
        suspects = []
        opened = False
        for L in located:
            if L.confidence >= LOCATED_AT and not any(i["cand"] == L.candidate.id for i in self._active()):
                await self._open_incident(L)
                opened = True
            else:
                suspects.append(L)
        if opened:
            self._rebuild()
        self.suspects = [{"id": L.candidate.id, "label": L.candidate.label, "confidence": round(L.confidence, 3),
                          "alternative": {"id": L.alternative.id, "label": L.alternative.label,
                                          "confidence": round(L.alt_confidence, 3)} if L.alternative else None,
                          "lat": L.candidate.lat, "lon": L.candidate.lon, "transformers": sorted(L.candidate.out),
                          "reasons": L.reasons} for L in suspects if L.confidence < LOCATED_AT]
        await self._maybe_ask(suspects)
        self._refresh_outages()
        self._score_and_plan()
        await self._dispatch()
        for inc in self._active():
            if inc["explained_kind"] != inc["kind"]:
                await self._explain(inc)
            if inc["kind"] != "unknown":
                await self._notify(inc)
        await self.broadcast({"type": "state", "state": self.snapshot(include_log=False)})

    def _score_and_plan(self) -> None:
        jobs = []
        work = self.work_zones()
        belief = self.belief()
        live_wire_safe = any(h["safe"] for h in self.hazards if h["kind"] == "live_wire")
        for inc in self.incidents:
            job = Job(inc["id"], inc["title"], inc["kind"], inc["lat"], inc["lon"], inc["customers_out"],
                      inc["confidence"], inc["critical"], inc["first_t"],
                      inc["kind"] == "live_wire" and not live_wire_safe)
            score(job, None if inc["status"] == "restored" else self.elapsed)
            inc["priority"], inc["breakdown"] = job.priority, job.breakdown
            jobs.append(job)
            if inc["status"] != "restored" and inc["site_section"] and inc["kind"] in SECTION_KINDS:
                device = next((d for d in inc["devices"] if d in self.config_open), None)
                plans = restoration_plans(self.feeder, belief, inc["site_section"], device, work, self.customers)
                mine = set(inc["out"])
                # Offer what concerns this fault: plans that restore its customers, or shortcuts that would hit it.
                inc["plans"] = [p.__dict__ for p in plans if (p.safe and mine & set(p.restores)) or (
                    not p.safe and inc["site_section"] in p.reason)]
            else:
                inc["plans"] = []
            inc["eta"] = self._eta(inc)
        # What-if from the storm's start: GridMedic's ranked plan vs first-call-first-served.
        crews = [Crew(c["id"], c["name"], c["skills"], *self.feeder.bus_pos[c["base"]]) for c in self.crews.values()]
        self.plan = schedule(jobs, crews)
        self.baseline = schedule(jobs, crews, baseline=True)

    def _eta(self, inc: dict) -> float | None:
        if inc["status"] == "restored":
            return inc["restored_at"]
        t = self.elapsed
        for s in inc["steps"]:
            if s["status"] == "done":
                continue
            t = max(t, s["end_t"]) if s.get("end_t") else t + (15 + s["minutes"]) * 60
        return t

    # ---- crews: dispatch, travel, work, restore -------------------------------------------

    def _travel_s(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return haversine_m(a, b) * ROAD_FACTOR / 1000 / SPEED_KMH * 3600

    async def _dispatch(self) -> None:
        """Send idle crews to the next waiting step of the highest-priority incidents."""
        for inc in sorted(self._active(), key=lambda i: -i["priority"]):
            step = next((s for s in inc["steps"] if s["status"] != "done"), None)
            if step is None or step["status"] != "pending":
                continue
            idle = [c for c in self.crews.values() if c["status"] == "idle" and set(step["skills"]) <= c["skills"]]
            if not idle:
                continue
            crew = min(idle, key=lambda c: self._travel_s((c["lat"], c["lon"]), (inc["lat"], inc["lon"])))
            travel = self._travel_s((crew["lat"], crew["lon"]), (inc["lat"], inc["lon"]))
            step.update(status="enroute", crew=crew["id"], depart_t=self.elapsed, arrive_t=self.elapsed + travel,
                        end_t=self.elapsed + travel + step["minutes"] * 60, from_=(crew["lat"], crew["lon"]))
            crew.update(status="enroute", incident=inc["id"], step=step["task"])
            if inc["status"] == "located":
                inc["status"] = "dispatched"
            await self.log("Code", f"Dispatched {crew['name']} to {inc['id']}: {step['task']}",
                           f"{inc['title']} at {inc['label']}; arrives {self.clock(step['arrive_t'])} "
                           f"({travel / 60:.0f} min drive)", inc["id"])

    def _next_transition(self, until: float):
        best = None
        for inc in self._active():
            for s in inc["steps"]:
                if s["status"] == "enroute" and s["arrive_t"] <= until:
                    cand = (s["arrive_t"], "arrive", inc, s)
                elif s["status"] == "onsite" and s["end_t"] <= until:
                    cand = (s["end_t"], "finish", inc, s)
                else:
                    continue
                if best is None or cand[0] < best[0]:
                    best = cand
        return best

    async def advance(self, until: float) -> None:
        """Move the clock forward, processing crew arrivals and finished work in time order."""
        changed = False
        while (tr := self._next_transition(until)) is not None:
            t, what, inc, step = tr
            self._tick_cmi(t)
            self.elapsed = max(self.elapsed, t)
            crew = self.crews[step["crew"]]
            if what == "arrive":
                step["status"] = "onsite"
                crew.update(status="onsite", lat=inc["lat"], lon=inc["lon"])
                inc["status"] = "on site"
                await self.log("Crew", f"{crew['name']} on site at {inc['id']}", f"{step['task']} at {inc['label']}",
                               inc["id"])
                if not inc.get("site_reported") and self.sim:
                    inc["site_reported"] = True
                    self.sim.crew_arrived(self._info(inc), crew["name"], self.elapsed)
            else:
                step["status"] = "done"
                crew.update(status="idle", incident=None, step=None)
                await self.log("Crew", f"{crew['name']} finished: {step['task']}", inc["label"], inc["id"])
                if step["task"] == "make safe and cordon off":
                    for h in self.hazards:
                        if h["kind"] == "live_wire" and haversine_m((h["lat"], h["lon"]), (inc["lat"], inc["lon"])) < 400:
                            h["safe"] = True
                    await self.log("Crew", "Live wire made safe", "area cordoned; the hazard no longer ranks first",
                                   inc["id"])
                if all(s["status"] == "done" for s in inc["steps"]):
                    if inc["kind"] == "unknown" and any(d in self.config_open for d in inc["devices"]) \
                            and inc.setdefault("patrols", 1) < 3:
                        inc["patrols"] += 1
                        inc["steps"].append({"skills": ["troubleshooter"], "minutes": 30, "status": "pending",
                                             "crew": None, "task": f"patrol located zone ({inc['patrols']})"})
                        inc["site_reported"] = False
                        await self.log("Crew", f"{inc['id']}: nothing found yet, device still locked out",
                                       "extending the patrol", inc["id"])
                    elif inc["kind"] == "unknown":
                        inc["status"], inc["restored_at"] = "restored", self.elapsed
                        await self.log("Crew", f"{inc['id']} closed: patrol found no damage", inc["label"], inc["id"])
                        if self.sim:  # anyone still dark will call again, which reopens the search
                            self.sim.restored(list(inc["out"]), self.elapsed)
                    else:
                        await self._complete(inc)
            changed = True
            self._refresh_outages()
            self._score_and_plan()
            await self._dispatch()
        self._tick_cmi(until)
        self.elapsed = max(self.elapsed, until)
        if self._dirty and self.elapsed - self._last_trace >= self.pack.get("retrace_s", 0):
            await self.recompute()
        elif changed:
            await self.broadcast({"type": "state", "state": self.snapshot(include_log=False)})

    async def _switch(self, op: str, dev: str, why: str) -> None:
        (self.config_open.discard if op == "close" else self.config_open.add)(dev)
        if self.sim:
            self.sim.switched(op, dev)
        await self.log("Operator" if why == "plan" else "Code", f"{op.capitalize()} {dev}", "" if why == "plan" else why)

    async def _complete(self, inc: dict) -> None:
        """Repair done: return any switching to normal, close the device, and tell customers."""
        before = live_transformers(self.feeder, self.belief())
        inc["repaired_truth"] = self.sim.repaired(self._info(inc)) if self.sim else None
        inc["status"], inc["restored_at"] = "restored", self.elapsed
        is_tie = lambda d: d in self.feeder.switches and self.feeder.switches[d].kind == "tie"  # noqa: E731
        # Undo the switching (ties first, so the feeders are never paralleled); the device closes last.
        undo = [("open" if op == "close" else "close", d) for op, d in reversed(inc["switching"])
                if d in self.feeder.switches]
        for op, dev in [u for u in undo if is_tie(u[1])] + [u for u in undo if not is_tie(u[1])]:
            await self._switch(op, dev, "back to normal configuration")
        for d in inc["devices"]:
            if d in self.config_open:
                await self._switch("close", d, "section repaired and crew clear")
        self.scada_owner = {d: i for d, i in self.scada_owner.items() if i != inc["id"]}
        after = live_transformers(self.feeder, self.belief())
        await self._restored(inc, sorted(after - before), f"{inc['title']} repaired")

    async def _restored(self, inc: dict, transformers: list[str], why: str) -> None:
        for t in transformers:
            self.restored_at[t] = self.elapsed
        accounts = set(inc["dead_customers"]) if inc["status"] == "restored" else set()
        n = sum(self.customers.get(t, 0) for t in transformers) + len(accounts)
        await self.log("Code", f"Power restored to {n} customers",
                       f"{why}; transformers {', '.join(transformers)}" if transformers else why, inc["id"])
        recipients = [m for m in self.messages if m.get("status") == "new" and m["channel"] != "crew" and m.get("from")
                      and ((m.get("location") or {}).get("transformer") in transformers
                           or (m.get("location") or {}).get("account") in accounts)]
        by_lang: dict[str, list[str]] = {}
        for m in recipients:
            by_lang.setdefault(m["language"] if m["language"] in self.loc["restored"] else "en", []).append(m["from"])
        for lang, to in by_lang.items():
            notice = {"id": f"U{len(self.notices) + 1}", "t": round(self.elapsed), "fault": inc["id"],
                      "language": lang, "text": self.loc["restored"][lang], "to": sorted(set(to)), "model": "Code (template)",
                      "kind": "restored"}
            self.notices.append(notice)
            await self.broadcast({"type": "notice", "notice": notice})
        if self.sim:
            xfs = transformers + sorted({self.db.by_account(a).transformer_id for a in accounts})
            self.sim.restored(xfs, self.elapsed)

    async def apply_plan(self, iid: str, plan_id: str) -> dict:
        """Operator approved a switching plan: re-check it now, then operate the switches in order."""
        inc = self._incident(iid)
        if inc is None:
            return {"ok": False, "reason": "no such incident"}
        self._score_and_plan()
        plan = next((p for p in inc["plans"] if p["id"] == plan_id), None)
        if plan is None or not plan["safe"]:
            reason = plan["reason"] if plan else "plan no longer offered"
            await self.log("Code", f"Refused: {plan['title'] if plan else plan_id}", reason, iid)
            return {"ok": False, "reason": reason}
        await self.log("Operator", f"Approved: {plan['title']}", plan["reason"], iid)
        before = live_transformers(self.feeder, self.belief())
        for op, dev in plan["steps"]:
            await self._switch(op, dev, "plan")
            inc["switching"].append((op, dev))
        restored = sorted(live_transformers(self.feeder, self.belief()) - before)
        await self._restored(inc, restored, f"switched around section {inc['site_section']}")
        await self.recompute()
        return {"ok": True, "restored": restored}

    # ---- agent outputs ----------------------------------------------------------------

    async def _explain(self, inc: dict) -> None:
        """Muse Spark turns the tracer's facts into a dispatcher-facing sentence (once per diagnosis)."""
        inc["explained_kind"] = inc["kind"]
        steps = "; ".join(s["task"] for s in inc["steps"] if s["status"] != "done")
        facts = (f"Fault: {inc['title']} at {inc['label']}. Confidence {inc['confidence']:.0%}. "
                 f"Evidence: {'; '.join(inc['reasons'])}. Customers out: {inc['customers_out']}. "
                 f"Critical loads: {', '.join(inc['critical']) or 'none'}. "
                 f"Crew findings: {inc['history'][-1]['after'] if inc['history'] else 'none yet'}. "
                 f"Work planned: {steps or 'none'}.")
        text, model = None, "Muse Spark"
        if not self.offline:
            try:
                text = await asyncio.to_thread(self.client.spark_text, EXPLAIN_SYSTEM, facts)
            except Exception:  # noqa: BLE001
                text = None
        if not text:
            model = "mock (template)"
            why = (inc["history"][-1]["after"] + " (crew report)") if inc["history"] else (
                inc["reasons"][0] if inc["reasons"] else "evidence matches")
            text = f"{inc['title']} at {inc['label']}: {why}. Work: {steps or 'none'}."
        inc["explanation"], inc["explanation_model"] = text.strip(), model
        await self.log(model, f"Why {inc['id']}: {inc['title'].lower()}", inc["explanation"], inc["id"])

    async def _notify(self, inc: dict) -> None:
        """Tell every customer who reported this fault when their power should be back, in their language."""
        if inc["eta"] is None:
            return
        eta = self.clock(inc["eta"])
        recipients = [m for m in self.messages if m.get("status") == "new" and m["id"] in inc["reports"]
                      and m["channel"] != "crew" and m.get("from") and m["from"] not in inc["notified"]]
        if not recipients:
            return
        first = not inc["notified"]
        by_lang: dict[str, list[str]] = {}
        for m in recipients:
            by_lang.setdefault(m["language"] if m["language"] in self.loc["notice"] else "en", []).append(m["from"])
            inc["notified"].append(m["from"])
        for lang, to in by_lang.items():
            kind = KIND_TITLE[inc["kind"]].lower()
            text, model = None, "Muse Spark"
            if not self.offline:
                try:
                    text = await asyncio.to_thread(
                        self.client.spark_text, NOTICE_SYSTEM,
                        f"Language: {LANG_NAME[lang]}. Fault type: {kind}. Estimated restoration: {eta}.")
                except Exception:  # noqa: BLE001
                    text = None
            if not text:
                text, model = self.loc["notice"][lang].format(kind=kind, eta=eta), "mock (template)"
            notice = {"id": f"U{len(self.notices) + 1}", "t": round(self.elapsed), "fault": inc["id"], "language": lang,
                      "text": text.strip(), "to": sorted(set(to)), "model": model, "kind": "eta"}
            self.notices.append(notice)
            await self.broadcast({"type": "notice", "notice": notice})
        if first:
            await self.log("Agent", f"Restoration time sent to {len(recipients)} customers",
                           f"{inc['title']}: back around {eta}; languages {', '.join(sorted(by_lang))}", inc["id"])

    async def _maybe_ask(self, located) -> None:
        """Ask the customer whose answer best separates the top explanation from its rival."""
        claimed = {t for i in self._active() for t in i["out"]}
        for L in located:
            if L.confidence >= ASK_BELOW or L.alternative is None:
                continue
            c, alt = L.candidate, L.alternative
            if any(p["fault"] == c.id and (p.get("answer") is None or self.elapsed - p["t"] < PROBE_GAP_S)
                   for p in self.probes):
                continue
            diff = (c.out ^ alt.out) - set(self.ev.reports) - set(self.ev.probes) - claimed
            if not diff:
                continue
            reported = [self.feeder.transformers[t] for t in c.out if t in self.ev.reports]

            def dist(tid):
                t = self.feeder.transformers[tid]
                return min(haversine_m((t.lat, t.lon), (r.lat, r.lon)) for r in reported) if reported else 0

            target = min(diff, key=dist)
            customers = [x for x in self.db.customers_on(target) if not x.critical]
            if not customers:
                continue
            who = customers[len(self.probes) % len(customers)]
            langs = [self.languages[t] for t in c.out if t in self.languages]
            lang = langs[-1] if langs else "en"
            probe = {"id": f"Q{len(self.probes) + 1}", "t": round(self.elapsed), "fault": c.id, "rival": alt.id,
                     "transformer": target, "to": who.phone, "name": who.name, "street": who.street,
                     "house_no": who.house_no, "language": lang, "text": self.loc["question"].get(lang, self.loc["question"]["en"]),
                     "answer": None, "lat": who.lat, "lon": who.lon}
            self.probes.append(probe)
            only = c.id if target in c.out else alt.id
            await self.log("Agent", f"Asking {who.street} {who.house_no} (transformer {target})",
                           f"{c.id} {L.confidence:.0%} vs {alt.id} {L.alt_confidence:.0%}: their answer separates "
                           f"the two (only {only} would cut their supply)", probe["id"])
            await self.broadcast({"type": "probe", "probe": probe})
            if self.sim:
                self.sim.probe(probe)

    # ---- customer portal -----------------------------------------------------------------

    def customer_status(self, query: str) -> dict:
        q = (query or "").strip()
        c = self.db.by_account(q) or self.db.by_phone(q)
        if c is None:
            return {"found": False}
        active = next((i for i in self._active() if c.transformer_id in i["out"]
                       or c.account_no in i["dead_customers"]), None)
        if active:
            crew = next((self.crews[s["crew"]]["name"] for s in active["steps"]
                         if s["status"] in ("enroute", "onsite") and s.get("crew")), None)
            status = {"state": "outage", "fault": active["title"], "incident": active["id"], "crew": crew,
                      "crew_status": active["status"], "eta": self.clock(active["eta"]) if active["eta"] else None}
        elif c.transformer_id in self.restored_at:
            status = {"state": "restored", "at": self.clock(self.restored_at[c.transformer_id])}
        else:
            reported = any((m.get("location") or {}).get("account") == c.account_no for m in self.messages)
            status = {"state": "reported" if reported else "no_known_outage"}
        notices = [n for n in self.notices if c.phone in n["to"]]
        mine = [{"id": m["id"], "clock": self.clock(m["t"]), "text": m["text"]} for m in self.messages
                if (m.get("location") or {}).get("account") == c.account_no]
        return {"found": True, "customer": {"name": c.name, "account": c.account_no, "phone": c.phone,
                                            "address": f"{c.house_no} {c.street}", "transformer": c.transformer_id},
                "status": status, "notices": notices, "reports": mine}

    # ---- output ------------------------------------------------------------------

    def _info(self, inc: dict) -> dict:
        return {k: inc[k] for k in ("id", "kind", "label", "zone", "site_section", "site_xf", "out", "cand")}

    def busy(self) -> bool:
        return bool(self._active()) or any(c["status"] != "idle" for c in self.crews.values())

    def score_against_truth(self) -> list[dict]:
        out = []
        for tf in self.scenario["faults"]:
            hit = [i for i in self.incidents if tf["id"] in (i.get("truth"), i.get("repaired_truth"))]
            out.append({"id": tf["id"], "title": tf["title"], "found": any(i["kind"] == tf["kind"] for i in hit),
                        "located_at": min((i["located_at"] for i in hit), default=None),
                        "restored_at": next((i["restored_at"] for i in hit if i["restored_at"]), None),
                        "incident": hit[0]["id"] if hit else None})
        return out

    def crew_positions(self) -> list[dict]:
        crews = []
        for c in self.crews.values():
            inc = self._incident(c["incident"])
            lat, lon = c["lat"], c["lon"]
            if c["status"] == "enroute" and inc:
                step = next((s for s in inc["steps"] if s.get("crew") == c["id"] and s["status"] == "enroute"), None)
                if step:
                    k = min(max((self.elapsed - step["depart_t"]) / max(step["arrive_t"] - step["depart_t"], 1), 0), 1)
                    lat = step["from_"][0] + (inc["lat"] - step["from_"][0]) * k
                    lon = step["from_"][1] + (inc["lon"] - step["from_"][1]) * k
            crews.append({"id": c["id"], "name": c["name"], "status": c["status"], "incident": c["incident"],
                          "task": c["step"], "lat": lat, "lon": lon, "skills": sorted(c["skills"])})
        return crews

    def snapshot(self, include_log: bool = True) -> dict[str, Any]:
        crews = self.crew_positions()
        live = live_transformers(self.feeder, self.belief())
        dead = set(self.feeder.transformers) - live
        s = {
            "elapsed": self.elapsed, "clock": self.clock(self.elapsed), "mode": self.client.mode,
            "scenario": self.scenario["id"], "start_hour": self.pack["start_hour"],
            "offline": self.offline,
            "incidents": [_public_inc(i) for i in sorted(self.incidents, key=lambda i: (i["status"] == "restored",
                                                                                         -i["priority"]))],
            "suspects": self.suspects, "hazards": self.hazards, "probes": self.probes, "crews": crews,
            "plan": self.plan, "baseline": self.baseline, "open_devices": sorted(self.config_open),
            "dead_transformers": sorted(dead), "truth": self.score_against_truth(),
            "counts": {
                "messages": len(self.messages),
                "duplicates": sum(m.get("status") == "duplicate" for m in self.messages),
                "junk": sum(m.get("status") == "junk" for m in self.messages),
                "bd_sms": sum(m["model"] == self.sms_model for m in self.messages),
                "languages": dict(Counter(m["language"] for m in self.messages)),
                "model_calls": dict(self.model_calls),
                "notified": sum(len(n["to"]) for n in self.notices),
                "queued": len(self.queued),
                "meter_msgs": len(self.ami), "ami": (None if not self.meter_cov else self.ami_ok),
                "customers_out": sum(self.customers.get(t, 0) for t in dead)
                + sum(len(i["dead_customers"]) for i in self._active()),
                "incidents_open": len(self._active()),
                "cmi": round(self.cmi),
                "served": sum(self.customers.values()),
                "critical_out": sum(len(i["critical"]) for i in self._active()),
                "calls": sum(m["channel"] not in ("crew",) and not m.get("probe_reply") for m in self.messages),
                "crews": dict(Counter(c["status"] for c in self.crews.values())),
                "hazards_open": sum(not h["safe"] for h in self.hazards),
                "incidents_restored": len(self.incidents) - len(self._active()),
            },
        }
        if include_log:
            s["messages"] = [_public(m) for m in self.messages]
            s["timeline"], s["notices"] = self.timeline, self.notices
        return s


def _public(m: dict) -> dict:
    """Message as sent to the browser (without the raw scenario event and its labels)."""
    return {k: v for k, v in m.items() if k != "event"}


def _public_inc(i: dict) -> dict:
    return {k: v for k, v in i.items() if k not in ("damage", "truth", "repaired_truth")}
