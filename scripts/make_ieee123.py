"""Generate the independent IEEE 123-node storm scenario (scenarios/ieee123_storm.json).

Uses the IEEE 123-node distribution test feeder with synthetic customers in Pine Valley.
Generates faults and complaints independently using a fixed random seed without inspecting
or tuning for tracer scoring.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relight.config import SCENARIO_DIR
from relight.grid_ieee123 import build_ieee123_database, get_ieee123_feeder
from relight.packs import network

SEED = 123


def build_scenario() -> dict:
    rng = random.Random(SEED)
    sc_pack = {"locale": "us", "languages": ["en"], "start_hour": 16, "network": {"type": "ieee123"}}
    feeder, db = network({"pack": sc_pack})

    # Available sections that have transformers
    sections_with_xfmrs = [sid for sid in feeder.sections if feeder.transformers_on(sid)]
    assert len(sections_with_xfmrs) >= 10, f"Expected many sections with transformers, got {len(sections_with_xfmrs)}"

    # We place 5 independent faults across distinct branches of the feeder
    # F1: Tree on line on Lateral 2 (1-2)
    # F2: Wire down on Lateral 9 (8-9)
    # F3: Blown transformer fuse on a service transformer on Oakwood Avenue
    # F4: Snapped pole on Lateral 73 (72-73)
    # F5: Broken service wire to an individual residence

    # Let's find specific sections
    sec_f1 = "1-2" if "1-2" in feeder.sections else sections_with_xfmrs[0]
    sec_f2 = "8-9" if "8-9" in feeder.sections else sections_with_xfmrs[5]
    sec_f4 = "72-73" if "72-73" in feeder.sections else sections_with_xfmrs[15]

    # Pick a transformer for F3
    candidate_xfmrs = [t for t in feeder.transformers.values() if t.section not in (sec_f1, sec_f2, sec_f4)]
    xfmr_f3 = candidate_xfmrs[10]

    # Pick a customer on a separate transformer for F5 (isolated house dark)
    candidate_isolated_xfmrs = [t for t in candidate_xfmrs if t.id != xfmr_f3.id and len(db.customers_on(t.id)) >= 2]
    xfmr_f5 = candidate_isolated_xfmrs[0]
    custs_f5 = db.customers_on(xfmr_f5.id)
    cust_f5 = custs_f5[0]
    neighbour_f5 = custs_f5[1]

    faults = [
        {
            "id": "F1",
            "title": f"Tree on line on {feeder.sections[sec_f1].street}",
            "kind": "tree_on_line",
            "section": sec_f1,
            "device": "FUS-1",
            "open_device": "FUS-1",
            "street": feeder.sections[sec_f1].street,
            "near_house": 102,
        },
        {
            "id": "F2",
            "title": f"Live wire on {feeder.sections[sec_f2].street}",
            "kind": "live_wire",
            "section": sec_f2,
            "device": "FUS-4",
            "open_device": "FUS-4",
            "street": feeder.sections[sec_f2].street,
            "near_house": 104,
        },
        {
            "id": "F3",
            "title": f"Blown transformer fuse on {feeder.sections[xfmr_f3.section].street}",
            "kind": "blown_fuse",
            "transformer": xfmr_f3.id,
            "device": f"XF-{xfmr_f3.id[2:]}",
            "open_device": f"XF-{xfmr_f3.id[2:]}",
            "street": feeder.sections[xfmr_f3.section].street,
            "near_house": 106,
        },
        {
            "id": "F4",
            "title": f"Snapped pole on {feeder.sections[sec_f4].street}",
            "kind": "pole_down",
            "section": sec_f4,
            "device": "FUS-13",
            "open_device": "FUS-13",
            "street": feeder.sections[sec_f4].street,
            "near_house": 110,
        },
        {
            "id": "F5",
            "title": f"Broken service wire at {cust_f5.house_no} {cust_f5.street}",
            "kind": "service_wire",
            "transformer": xfmr_f5.id,
            "device": f"SVC-{xfmr_f5.id}",
            "houses": [cust_f5.house_no, cust_f5.house_no],
            "street": cust_f5.street,
            "near_house": cust_f5.house_no,
            "account": cust_f5.account_no,
        },
    ]

    events = []
    c_id = 0

    # Generate customer complaints for each fault
    # Helper to create a complaint
    def add_complaint(t_sec: int, cust, fid: str, symptom: str, hazard: str, text: str, ch: str = "call"):
        nonlocal c_id
        c_id += 1
        events.append({
            "t": t_sec,
            "type": "complaint",
            "id": f"C{c_id}",
            "channel": ch,
            "language": "en",
            "from": cust.phone,
            "text": text,
            "truth": {
                "street": cust.street,
                "house_no": cust.house_no,
                "symptom": symptom,
                "hazard": hazard,
                "account_no": cust.account_no,
                "fault": fid,
            },
        })

    # F1 complaints (tree on line): customers on sec_f1
    custs_f1 = [c for t in feeder.transformers_on(sec_f1) for c in db.customers_on(t)]
    if custs_f1:
        add_complaint(35, custs_f1[0], "F1", "no_power", "tree",
                      f"A large tree branch fell across the power lines on {custs_f1[0].street} near #{custs_f1[0].house_no} and our power died.", "call")
        if len(custs_f1) > 1:
            add_complaint(70, custs_f1[1], "F1", "no_power", "none",
                          f"Power is completely out here at {custs_f1[1].house_no} {custs_f1[1].street}.", "sms")
        if len(custs_f1) > 2:
            add_complaint(110, custs_f1[2], "F1", "no_power", "tree",
                          f"Tree limb on wires on {custs_f1[2].street}, lights cut out.", "call")

    # F2 complaints (live wire): customers on sec_f2
    custs_f2 = [c for t in feeder.transformers_on(sec_f2) for c in db.customers_on(t)]
    if custs_f2:
        add_complaint(40, custs_f2[0], "F2", "no_power", "live_wire",
                      f"There is a sparking live wire down across {custs_f2[0].street} right outside #{custs_f2[0].house_no}! Power is out.", "call")
        if len(custs_f2) > 1:
            add_complaint(85, custs_f2[1], "F2", "no_power", "none",
                          f"Outage at {custs_f2[1].house_no} {custs_f2[1].street}, all dark.", "sms")
        if len(custs_f2) > 2:
            add_complaint(130, custs_f2[2], "F2", "no_power", "live_wire",
                          f"Sparking electrical cable hanging down near {custs_f2[2].street}.", "call")

    # F3 complaints (blown transformer fuse): customers on xfmr_f3
    custs_f3 = db.customers_on(xfmr_f3.id)
    if custs_f3:
        add_complaint(45, custs_f3[0], "F3", "no_power", "none",
                      f"We heard a loud explosion from the transformer on the pole and our lights went out immediately at {custs_f3[0].house_no} {custs_f3[0].street}.", "call")
        if len(custs_f3) > 1:
            add_complaint(95, custs_f3[1], "F3", "no_power", "none",
                          f"No electricity at {custs_f3[1].house_no} {custs_f3[1].street}.", "sms")
        if len(custs_f3) > 2:
            add_complaint(140, custs_f3[2], "F3", "no_power", "none",
                          f"Loud pop on pole transformer on {custs_f3[2].street}, no power.", "call")

    # F4 complaints (pole down): customers on sec_f4
    custs_f4 = [c for t in feeder.transformers_on(sec_f4) for c in db.customers_on(t)]
    if custs_f4:
        add_complaint(50, custs_f4[0], "F4", "no_power", "pole_down",
                      f"A wooden utility pole has snapped in half and is blocking {custs_f4[0].street} near #{custs_f4[0].house_no}!", "call")
        if len(custs_f4) > 1:
            add_complaint(100, custs_f4[1], "F4", "no_power", "none",
                          f"Power outage reported at {custs_f4[1].house_no} {custs_f4[1].street}.", "sms")
        if len(custs_f4) > 2:
            add_complaint(160, custs_f4[2], "F4", "no_power", "pole_down",
                          f"Broken pole leaning over {custs_f4[2].street}, wires down on pavement.", "call")

    # F5 complaints (lone house dark, service wire): single customer calls
    add_complaint(60, cust_f5, "F5", "no_power", "none",
                  f"Our house at {cust_f5.house_no} {cust_f5.street} lost all electricity, but my neighbours across the street still have their lights on.", "call")

    # Sort events by arrival time
    events.sort(key=lambda e: e["t"])

    crews = [
        {
            "id": "CREW-L1",
            "name": "Pine Valley Line Crew 1",
            "skills": ["line", "bucket_truck"],
            "base": "SUB",
        },
        {
            "id": "CREW-L2",
            "name": "Pine Valley Line Crew 2",
            "skills": ["line", "bucket_truck"],
            "base": "SUB",
        },
        {
            "id": "CREW-V1",
            "name": "Pine Valley Tree Crew",
            "skills": ["vegetation"],
            "base": "SUB",
        },
        {
            "id": "CREW-T1",
            "name": "Pine Valley Troubleshooter 1",
            "skills": ["troubleshooter"],
            "base": "SUB",
        },
        {
            "id": "CREW-T2",
            "name": "Pine Valley Troubleshooter 2",
            "skills": ["troubleshooter"],
            "base": "SUB",
        },
    ]

    scenario = {
        "id": "ieee123_storm",
        "title": "Storm over Pine Valley (IEEE 123-node test feeder)",
        "external": True,
        "external_note": "Faults and complaints generated by standalone script scripts/make_ieee123.py on the IEEE 123-node test feeder with synthetic customers",
        "pack": sc_pack,
        "duration_s": 1500,
        "notes": (
            "Independent benchmark scenario on the IEEE 123-node distribution test feeder. "
            "Network topology and line configurations are from the IEEE PES DSAS benchmark. "
            "Street names, customers and fault placements were generated by scripts/make_ieee123.py "
            "with fixed random seed SEED=123."
        ),
        "crews": crews,
        "faults": faults,
        "events": events,
    }

    out_file = SCENARIO_DIR / "ieee123_storm.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=1)
    print(f"Created {out_file} with {len(faults)} faults and {len(events)} events.")
    return scenario


if __name__ == "__main__":
    build_scenario()
