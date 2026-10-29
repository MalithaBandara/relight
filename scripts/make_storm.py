"""Generate storm scenarios on feeders built from real OpenStreetMap roads.

Faults are placed on the generated network by rule (a tree in the switchable zone, poles
down behind lateral fuses, a live wire, transformer fuses, a service wire that looks like a
fuse, a fault hidden behind another). Complaints come from the customers who really lose
power, in the locale's languages and channels, with duplicates, junk and SMS codes. Smart
meters (where the pack has them) send last-gasp messages until the meter network fails.

Usage:  python scripts/make_storm.py houston_hurricane chennai_cyclone
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight import packs  # noqa: E402
from relight.config import SCENARIO_DIR  # noqa: E402
from relight.network import NetworkState, live_transformers  # noqa: E402

TEXT = {
    "us": {
        "no_power": {"en": ["Power's out at {house} {street}.", "No electricity at {house} {street} since the storm.",
                            "Lights went out on {street}, house {house}.", "Outage at {house} {street}, please help."],
                     "es": ["Se fue la luz en el {house} de {street}.", "No hay electricidad en {house} {street} desde la tormenta.",
                            "Estamos sin luz en {street}, casa {house}."]},
        "partial_power": {"en": ["Lights are dim and flickering at {house} {street}.", "Half the house has power at {house} {street}."],
                          "es": ["La luz está muy baja en {house} {street}.", "Solo tenemos media casa con luz, {house} {street}."]},
        "live_wire": {"en": ["There's a power line down and sparking in front of {house} {street}!"],
                      "es": ["¡Hay un cable caído echando chispas frente al {house} de {street}!"]},
        "tree_on_line": {"en": ["A tree took down the lines on {street} near {house}. No power."],
                         "es": ["Un árbol tumbó los cables en {street} cerca del {house}."]},
        "pole_down": {"en": ["A power pole snapped on {street} by {house}, wires on the ground."],
                      "es": ["Se cayó un poste de luz en {street} cerca del {house}."]},
        "junk": {"en": ["Can you fix my wifi router?", "Congrats! You won a $500 gift card, click the link",
                        "How do I pay my bill online?"]},
        "channels": ["call", "sms", "app"],
    },
    "india": {
        "no_power": {"en": ["No power at door no {house}, {street}.", "Current illa since morning, {street} {house}.",
                            "Power cut in {street}, house {house}. Please send lineman.", "{street} {house} no current, fridge stopped."],
                     "ta": ["{street}, கதவு எண் {house}, கரண்ட் இல்லை.", "{street} {house} மின்சாரம் இல்லை, தயவு செய்து சரி செய்யவும்."],
                     "hi": ["{street}, मकान नंबर {house} में बिजली नहीं है।"]},
        "partial_power": {"en": ["Low voltage at {street} {house}, fan running slow.", "Single phase only at door no {house}, {street}."],
                          "ta": ["{street} {house}, வோல்டேஜ் குறைவாக உள்ளது."], "hi": ["{street} {house} में वोल्टेज बहुत कम है।"]},
        "live_wire": {"en": ["Wire fallen on road and sparking near door no {house}, {street}! Very dangerous."],
                      "ta": ["{street} {house} அருகில் மின் கம்பி சாலையில் விழுந்து தீப்பொறி வருகிறது!"],
                      "hi": ["{street} {house} के पास तार सड़क पर गिरा है और चिंगारी निकल रही है!"]},
        "tree_on_line": {"en": ["Tree fallen on EB line at {street} near {house}."],
                         "ta": ["{street} {house} அருகில் மரம் மின் கம்பியில் விழுந்துள்ளது."], "hi": ["{street} {house} के पास पेड़ बिजली के तार पर गिरा है।"]},
        "pole_down": {"en": ["EB pole fallen at {street} near door no {house}."],
                      "ta": ["{street} {house} அருகில் மின் கம்பம் விழுந்துவிட்டது."], "hi": ["{street} {house} के पास बिजली का खंभा गिर गया है।"]},
        "junk": {"en": ["Recharge offer 299 unlimited calls!!", "When is the next bill date?", "Water not coming in tap please check"]},
        "channels": ["call", "whatsapp", "sms"],
    },
}

SCENARIOS = {
    "houston_hurricane": {
        "title": "Hurricane landfall over Spring Branch, Houston",
        "pack": {"locale": "us", "languages": ["en", "es"], "language_weights": [0.75, 0.25], "start_hour": 21,
                 "network": {"type": "osm", "area": "houston", "transformer_spacing": 70, "substation_bearing": 270,
                             "reclosers": 3, "substation_label": "Spring Branch substation",
                             "feeder2_label": "Feeder 2 (Long Point side)", "unnamed": "Unnamed street"},
                 "smart_meters": {"coverage": 0.95, "delay_s": [5, 45], "network_fail_t": 600}},
        "duration_s": 1500, "seed": 11, "call_rate": 0.22, "dup_rate": 0.25, "junk": 4, "code_share": 0.25,
        "crews": [
            {"id": "CREW-L1", "name": "Line crew 1", "skills": ["line", "bucket_truck"], "base": "SUB"},
            {"id": "CREW-L2", "name": "Line crew 2", "skills": ["line", "bucket_truck"], "base": "SUB"},
            {"id": "CREW-V1", "name": "Tree crew", "skills": ["vegetation"], "base": "SUB"},
            {"id": "CREW-T1", "name": "Troubleshooter 1", "skills": ["troubleshooter"], "base": "SUB"},
            {"id": "CREW-T2", "name": "Troubleshooter 2", "skills": ["troubleshooter"], "base": "SUB"}],
        "faults": [
            {"kind": "tree_on_line", "where": "switch_zone", "t": 40},
            {"kind": "pole_down", "where": "fuse", "n": 0, "t": 120},
            {"kind": "blown_fuse", "where": "transformer", "n": 0, "t": 200},
            {"kind": "live_wire", "where": "line", "n": 0, "t": 480},
            {"kind": "pole_down", "where": "fuse", "n": 1, "t": 700},  # after the meter network fails
            {"kind": "service_wire", "where": "transformer", "n": 1, "t": 760, "houses": 6},
            {"kind": "blown_fuse", "where": "hidden", "behind": 1, "t": 120, "hidden": True},
        ],
    },
    "chennai_cyclone": {
        "title": "Cyclone over Velachery, Chennai",
        "pack": {"locale": "india", "languages": ["en", "ta", "hi"], "language_weights": [0.5, 0.42, 0.08],
                 "start_hour": 18, "quiet_messages": True, "retrace_s": 15,
                 "network": {"type": "osm", "area": "chennai", "transformer_spacing": 150, "substation_bearing": 200,
                             "reclosers": 4, "multi_unit_share": 0.35, "units_multi": [4, 16],
                             "substation_label": "Velachery 33/11 kV substation",
                             "feeder2_label": "Feeder 2 (Taramani side)", "unnamed": "Unnamed street"}},
        "duration_s": 1800, "seed": 23, "call_rate": 0.16, "dup_rate": 0.35, "junk": 20, "code_share": 0.3,
        "crews": [
            {"id": "CREW-L1", "name": "Line gang 1", "skills": ["line", "bucket_truck"], "base": "SUB"},
            {"id": "CREW-L2", "name": "Line gang 2", "skills": ["line", "bucket_truck"], "base": "SUB"},
            {"id": "CREW-L3", "name": "Line gang 3", "skills": ["line"], "base": "SUB"},
            {"id": "CREW-V1", "name": "Tree cutting team", "skills": ["vegetation"], "base": "SUB"},
            {"id": "CREW-T1", "name": "Lineman 1", "skills": ["troubleshooter"], "base": "SUB"},
            {"id": "CREW-T2", "name": "Lineman 2", "skills": ["troubleshooter"], "base": "SUB"},
            {"id": "CREW-T3", "name": "Lineman 3", "skills": ["troubleshooter"], "base": "SUB"}],
        "faults": [
            {"kind": "tree_on_line", "where": "switch_zone", "t": 60},
            {"kind": "pole_down", "where": "fuse", "n": 0, "t": 150},
            {"kind": "pole_down", "where": "fuse", "n": 1, "t": 260},
            {"kind": "tree_on_line", "where": "fuse", "n": 2, "t": 330},
            {"kind": "live_wire", "where": "line", "n": 0, "t": 420},
            {"kind": "blown_fuse", "where": "transformer", "n": 0, "t": 500},
            {"kind": "blown_fuse", "where": "transformer", "n": 1, "t": 640},
            {"kind": "pole_down", "where": "fuse", "n": 3, "t": 760},
            {"kind": "blown_fuse", "where": "transformer", "n": 2, "t": 900},
        ],
    },
}


def pick_sites(cfg, feeder, db, rng):
    """Resolve each fault's `where` rule to a concrete place on this feeder."""
    n = db.counts_by_transformer()
    fuses = [d for d in feeder.devices.values() if d.kind == "fuse" and len(feeder.downstream[d.id]) >= 2
             and sum(n.get(t, 0) for t in feeder.downstream[d.id]) >= 15]
    rng.shuffle(fuses)
    sw = [s for s in feeder.switches.values() if s.kind == "switch"]
    rec = next(d for d in feeder.devices.values() if d.kind == "recloser")
    covered: set[str] = set()  # transformers already dark from an earlier fault; separate faults stay apart

    def dark_area(sec=None, device=None):
        st = NetworkState(open=set(feeder.normally_open) | ({device} if device else set()),
                          faulted={sec} if sec else set())
        return set(feeder.transformers) - live_transformers(feeder, st)

    out = []
    for i, f in enumerate(cfg["faults"]):
        f = dict(f)
        f["id"] = f"F{i + 1}"
        if f["where"] == "switch_zone":
            # A section strictly between the two sectionalising switches, under the first recloser.
            a, b = sw[0].section, sw[1].section
            fused = {x for d in feeder.devices.values() if d.kind == "fuse" for x in feeder.sections_below(d.section)}
            # On the main run between the two switches, so opening both isolates it.
            path, x = [], feeder.parent_section.get(feeder.sections[b].from_bus)
            while x and x != a:
                path.append(x)
                x = feeder.parent_section.get(feeder.sections[x].from_bus)
            path.append(a)
            between = [s for s in path if feeder.transformers_on(s) and s not in fused] or path
            f["section"] = between[len(between) // 2]
            f["device"] = rec.id
            f["scada"] = rec.id
        elif f["where"] == "fuse":
            d = next(x for x in fuses if not feeder.downstream[x.id] & covered)
            fuses.remove(d)
            secs = [s for s in feeder.sections_below(d.section) if feeder.transformers_on(s)]
            f["section"] = secs[min(1, len(secs) - 1)]
            f["device"] = f["open_device"] = d.id
        elif f["where"] == "line":
            # An unprotected line section near the end of a branch: no device on it, as many customers as possible.
            dev_secs = {d.section for d in feeder.devices.values() if d.kind != "xfmr_fuse"}
            cands = [s for s in feeder.sections if feeder.transformers_on(s) and s not in dev_secs
                     and len(feeder.sections_below(s)) <= 3 and not dark_area(sec=s) & covered
                     and sum(n.get(t, 0) for t in dark_area(sec=s)) >= 25]
            cands.sort(key=lambda s: -len(feeder.transformers_on(s)))
            f["section"] = rng.choice(cands[:8])
            f["device"] = f"LINE-{f['section']}"
        elif f["where"] in ("transformer", "hidden"):
            if f["where"] == "hidden":
                pool = [t for s in feeder.sections_below(out[f["behind"]]["section"])
                        for t in feeder.transformers_on(s)][2:]
            else:
                pool = list(feeder.transformers)
            pool = [t for t in pool if n.get(t, 0) >= (6 if f["kind"] == "service_wire" else 3)
                    and (f["where"] == "hidden" or t not in covered)]
            t = rng.choice(pool)
            f["transformer"] = t
            f["device"] = f"XF-{t[2:]}" if f["kind"] == "blown_fuse" else f"SVC-{t}"
            if f["kind"] == "service_wire":
                houses = sorted({c.house_no for c in db.customers_on(t) if not c.critical})
                k = f.pop("houses")
                start = rng.randrange(0, max(len(houses) - k, 1))
                f["houses"] = [houses[start], houses[min(start + k - 1, len(houses) - 1)]]
        sec = f.get("section") or feeder.transformers[f["transformer"]].section
        f["street"] = feeder.sections[sec].street
        if not f.get("hidden"):
            covered |= dark_area(f.get("section"), f.get("scada") or f.get("open_device")) if "section" in f                 else {f["transformer"]}
        out.append(f)
    return out


def dead_accounts(feeder, db, f) -> list:
    st = NetworkState(open=set(feeder.normally_open))
    if "section" in f:
        st.faulted.add(f["section"])
    if f.get("scada") or f.get("open_device"):
        st.open.add(f.get("scada") or f["open_device"])
    if f["kind"] == "blown_fuse":
        st.dead_transformers.add(f["transformer"])
    live = live_transformers(feeder, st)
    if f["kind"] == "service_wire":
        lo, hi = f["houses"]
        street = feeder.sections[feeder.transformers[f["transformer"]].section].street
        return [c for c in db.customers_on(f["transformer"]) if lo <= c.house_no <= hi and c.street == street]
    return [c for t in set(feeder.transformers) - live for c in db.customers_on(t)]


def make(name: str) -> None:
    cfg = SCENARIOS[name]
    sc = {"id": name, "title": cfg["title"], "pack": cfg["pack"], "duration_s": cfg["duration_s"],
          "crews": cfg["crews"], "notes": "Generated by scripts/make_storm.py on a feeder built from real "
          "OpenStreetMap roads and buildings. Customers, accounts and phone numbers are synthetic. 'truth' blocks "
          "are labels used only for scoring and mock mode."}
    feeder, db = packs.network(sc)
    rng = random.Random(cfg["seed"])
    locale = cfg["pack"]["locale"]
    texts = TEXT[locale]
    langs, weights = cfg["pack"]["languages"], cfg["pack"]["language_weights"]
    code = {"us": "OUT", "india": "PWR"}[locale]
    faults = pick_sites(cfg, feeder, db, rng)
    events = []
    seen_callers: dict[str, int] = {}
    n_complaint = 0
    hidden_dark = set()
    for f in faults:
        if f.get("hidden"):
            hidden_dark |= {c.account_no for c in dead_accounts(feeder, db, f)}
    for f in faults:
        if f.get("scada"):
            events += [{"t": f["t"], "type": "scada", "device": f["scada"], "event": "trip"},
                       {"t": f["t"] + 3, "type": "scada", "device": f["scada"], "event": "reclose"},
                       {"t": f["t"] + 7, "type": "scada", "device": f["scada"], "event": "lockout"}]
        if f.get("hidden"):
            continue  # its customers are already dark behind the outer fault
        dark = [c for c in dead_accounts(feeder, db, f) if c.account_no not in seen_callers]
        if f["kind"] == "service_wire":
            near = dark[len(dark) // 2] if dark else None
        else:
            sec_xf = feeder.transformers_on(f["section"]) if "section" in f else [f["transformer"]]
            near_pool = [c for t in sec_xf for c in db.customers_on(t) if not c.critical]
            near = near_pool[len(near_pool) // 2] if near_pool else (dark[0] if dark else None)
        f["near_house"] = near.house_no if near else 0
        partial = f["kind"] == "live_wire"
        # Small outages still get a couple of calls (people do call when only their street is dark).
        must = {c.account_no for c in rng.sample(dark, min(2, len(dark)))} if len(dark) < 30 else set()
        for c in dark:
            if c.account_no not in must and rng.random() > (0.9 if c.critical else cfg["call_rate"]):
                continue
            seen_callers[c.account_no] = 1
            t = f["t"] + 20 + rng.expovariate(1 / 240)
            if t > cfg["duration_s"] - 30:
                continue
            lang = rng.choices(langs, weights)[0]
            hazard = "none"
            symptom = "partial_power" if partial else "no_power"
            if near and c.transformer_id == near.transformer_id and f["kind"] in ("live_wire", "tree_on_line", "pole_down") \
                    and rng.random() < 0.35:
                hazard = f["kind"]
            if hazard != "none":
                text = rng.choice(texts[hazard].get(lang) or texts[hazard]["en"])
            elif rng.random() < cfg["code_share"]:
                text, lang = f"{code} {c.account_no}", "en"
            else:
                text = rng.choice(texts[symptom].get(lang) or texts[symptom]["en"])
            channel = "sms" if text.startswith(code) else rng.choice(texts["channels"])
            n_complaint += 1
            ev = {"t": round(t), "type": "complaint", "id": f"C{n_complaint}", "channel": channel, "language": lang,
                  "from": c.phone, "text": text.format(street=c.street, house=c.house_no),
                  "truth": {"street": c.street, "house_no": c.house_no, "symptom": symptom, "hazard": hazard,
                            "account_no": c.account_no, "fault": f["id"]}}
            events.append(ev)
            if rng.random() < cfg["dup_rate"]:
                n_complaint += 1
                again = dict(ev, id=f"C{n_complaint}", t=min(round(t + rng.uniform(120, 600)), cfg["duration_s"] - 5))
                again["truth"] = dict(ev["truth"], dup_of=ev["id"])
                events.append(again)
        if f["kind"] == "live_wire" and near:
            # A passer-by with no account calls about the sparking wire.
            n_complaint += 1
            lang = langs[0]
            events.append({"t": f["t"] + 60, "type": "complaint", "id": f"C{n_complaint}", "channel": "call",
                           "language": lang, "from": f"0{rng.randint(10**8, 10**9 - 1)}",
                           "text": rng.choice(texts["live_wire"][lang]).format(street=near.street, house=near.house_no),
                           "truth": {"street": near.street, "house_no": near.house_no, "symptom": "none",
                                     "hazard": "live_wire", "passer_by": True}})
    for i in range(cfg["junk"]):
        n_complaint += 1
        events.append({"t": rng.randint(60, cfg["duration_s"] - 60), "type": "complaint", "id": f"C{n_complaint}",
                       "channel": "sms", "language": "en", "from": f"0{rng.randint(10**8, 10**9 - 1)}",
                       "text": rng.choice(texts["junk"]["en"]), "truth": {"junk": True, "symptom": "none",
                                                                          "hazard": "none"}})

    meters = cfg["pack"].get("smart_meters")
    if meters:
        fail = meters["network_fail_t"]
        batches: dict[int, list[str]] = {}
        for f in faults:
            if f.get("hidden"):
                continue
            for c in dead_accounts(feeder, db, f):
                if rng.random() > meters["coverage"]:
                    continue
                t = f["t"] + rng.uniform(*meters["delay_s"])
                if t < fail:
                    batches.setdefault(int(t // 15) * 15 + 15, []).append(c.account_no)
        events += [{"t": t, "type": "ami", "accounts": sorted(set(a))} for t, a in sorted(batches.items())]
        events.append({"t": fail, "type": "ami_status", "ok": False,
                       "detail": "meter collectors lost power; last-gasp messages stopped"})
    events.sort(key=lambda e: e["t"])
    sc["faults"] = [{k: v for k, v in f.items() if k not in ("where", "n", "behind")} | {"title": _title(f)}
                    for f in faults]
    sc["events"] = events
    (SCENARIO_DIR / f"{name}.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    n_c = sum(e["type"] == "complaint" for e in events)
    print(f"{name}: {len(faults)} faults, {n_c} complaints, {sum(e['type'] == 'ami' for e in events)} meter batches, "
          f"{sum(db.counts_by_transformer().values())} customers")
    for f in sc["faults"]:
        print(f"   {f['id']} {f['title']}  device={f['device']}  t={f['t']}")


def _title(f) -> str:
    what = {"tree_on_line": "Tree on line", "pole_down": "Pole down", "blown_fuse": "Blown transformer fuse",
            "live_wire": "Live wire on road", "service_wire": "Service wire down (looks like a blown fuse)"}[f["kind"]]
    return f"{what} on {f['street']}" + (" (hidden behind another fault)" if f.get("hidden") else "")


if __name__ == "__main__":
    for n in sys.argv[1:] or list(SCENARIOS):
        make(n)
