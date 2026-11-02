"""IEEE 123-node test feeder builder and layout.

Converts the official IEEE 123-node distribution test feeder data (IEEE PES DSAS)
into a Feeder network spec and synthetic customer database.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

from .config import DATA_DIR
from .customers import CustomerDB, create_database
from .grid import Feeder, _move, bearing, polyline_length

ORIGIN = (34.0500, -84.2500)  # Made-up suburban location (Pine Valley)
SEED = 123

STREET_NAMES = [
    "Valley Main Road",
    "Pine Ridge Road",
    "Oakwood Avenue",
    "Maple Creek Lane",
    "Cedar Grove Drive",
    "Elmwood Court",
    "Willow Springs Road",
    "Forest Hill Drive",
    "Sunset Boulevard",
    "Meadow Lane",
    "River Road",
    "Highland Way",
    "Spring Valley Road",
    "Orchard Lane",
    "Hillside Drive",
    "Lakeview Terrace",
    "Birchwood Way",
    "Cypress Creek Road",
    "Aspen Court",
    "Sycamore Lane",
    "Magnolia Drive",
    "Chestnut Street",
    "Fairview Avenue",
    "Brookside Lane",
]

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
]

SURNAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
]

FUSE_LATERALS = [
    ("FUS-1", "1-2", "Lateral 2 fuse"),
    ("FUS-2", "1-3", "Lateral 3 fuse"),
    ("FUS-3", "3-4", "Branch 4 fuse"),
    ("FUS-4", "8-9", "Lateral 9 fuse"),
    ("FUS-5", "8-12", "Lateral 12 fuse"),
    ("FUS-6", "18-19", "Lateral 19 fuse"),
    ("FUS-7", "21-22", "Lateral 22 fuse"),
    ("FUS-8", "23-24", "Lateral 24 fuse"),
    ("FUS-9", "40-41", "Lateral 41 fuse"),
    ("FUS-10", "42-43", "Lateral 43 fuse"),
    ("FUS-11", "44-45", "Lateral 45 fuse"),
    ("FUS-12", "57-58", "Lateral 58 fuse"),
    ("FUS-13", "72-73", "Lateral 73 fuse"),
    ("FUS-14", "87-88", "Lateral 88 fuse"),
    ("FUS-15", "89-90", "Lateral 90 fuse"),
    ("FUS-16", "91-92", "Lateral 92 fuse"),
    ("FUS-17", "93-94", "Lateral 94 fuse"),
    ("FUS-18", "101-102", "Lateral 102 fuse"),
    ("FUS-19", "105-106", "Lateral 106 fuse"),
    ("FUS-20", "108-109", "Lateral 109 fuse"),
]


def load_dss_lines() -> list[tuple[str, str, str, float]]:
    """Parse IEEE 123 lines and switches from data/IEEE123Master.dss."""
    dss_path = DATA_DIR / "IEEE123Master.dss"
    lines = []
    with open(dss_path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"New Line\.(\w+)\s+.*Bus1=([\w\.]+)\s+Bus2=([\w\.]+)\s+.*Length=([\d\.]+)", line, re.I)
            if m:
                name, b1, b2, length = m.groups()
                b1 = b1.split(".")[0].replace("_OPEN", "")
                b2 = b2.split(".")[0].replace("_OPEN", "")
                lines.append((name, b1, b2, float(length)))

    # In-line regulators defined in DSS
    lines.append(("Reg1a", "150", "150r", 0.01))
    lines.append(("Reg2", "9", "9r", 0.01))
    lines.append(("Reg3", "25", "25r", 0.01))
    lines.append(("Reg4", "160", "160r", 0.01))
    return lines


def ieee123_spec(origin: tuple[float, float] = ORIGIN) -> dict:
    """Build the Feeder spec for IEEE 123-node system with geographic coordinates."""
    raw_lines = load_dss_lines()

    # Build undirected adjacency to traverse from root 150 downwards
    adj: dict[str, list[tuple[str, str, float]]] = {}
    for name, b1, b2, l in raw_lines:
        adj.setdefault(b1, []).append((b2, name, l))
        adj.setdefault(b2, []).append((b1, name, l))

    # Orient tree from root bus 150
    tree_edges: list[tuple[str, str, str, float]] = []
    visited = {"150"}
    queue = ["150"]
    while queue:
        curr = queue.pop(0)
        for nxt, name, l in adj.get(curr, []):
            if nxt not in visited and name not in ("Sw7", "Sw8"):
                visited.add(nxt)
                tree_edges.append((name, curr, nxt, l))
                queue.append(nxt)

    # Assign heading and street names deterministically
    buses: dict[str, tuple[float, float]] = {"150": origin, "SUB": origin}
    sections = []
    rng = random.Random(SEED)

    # Breadth-first coordinate assignment
    bus_children: dict[str, list[tuple[str, str, float]]] = {}
    for name, frm, to, l in tree_edges:
        bus_children.setdefault(frm, []).append((to, name, l))

    # Street names mapped by branch tree
    street_map: dict[str, str] = {"150": STREET_NAMES[0]}
    heading_map: dict[str, float] = {"150": 180.0}

    # Assign coordinates
    queue = ["150"]
    s_idx = 0
    while queue:
        u = queue.pop(0)
        chs = bus_children.get(u, [])
        u_heading = heading_map.get(u, 180.0)
        u_street = street_map.get(u, STREET_NAMES[0])

        for idx, (v, name, l_kft) in enumerate(chs):
            ft = l_kft * 1000.0
            dist_m = 80.0 + 2.5 * math.sqrt(ft) if ft > 10 else 15.0
            if len(chs) == 1:
                v_heading = (u_heading + rng.uniform(-10, 10)) % 360
                v_street = u_street
            else:
                # Branches fan out left and right
                angle_offset = -60.0 + idx * (120.0 / max(1, len(chs) - 1))
                v_heading = (u_heading + angle_offset) % 360
                s_idx = (s_idx + 1) % len(STREET_NAMES)
                v_street = STREET_NAMES[s_idx]

            heading_map[v] = v_heading
            street_map[v] = v_street
            buses[v] = _move(*buses[u], v_heading, dist_m)
            sec_id = f"{u}-{v}"
            sections.append({
                "id": sec_id,
                "from": u,
                "to": v,
                "coords": [buses[u], buses[v]],
                "street": v_street,
            })
            queue.append(v)

    # Protective devices
    devices = [
        ("BRK-1", "breaker", "150-150r", True, "Substation feeder breaker BRK-1"),
        ("REC-1", "recloser", "13-152", True, "Valley Main recloser REC-1"),
        ("REC-2", "recloser", "18-135", True, "Pine Ridge recloser REC-2"),
        ("REC-3", "recloser", "60-160", True, "Oakwood recloser REC-3"),
        ("REC-4", "recloser", "97-197", True, "Willow Springs recloser REC-4"),
    ]
    # Lateral fuses
    sec_ids = {s["id"] for s in sections}
    for fid, sid, flabel in FUSE_LATERALS:
        if sid in sec_ids:
            devices.append((fid, "fuse", sid, False, flabel))

    # Normally closed sectionalising switches
    switches = [
        ("SW-1", "switch", "150r-149", False, "Main sectionalising switch SW-1"),
        ("SW-2", "switch", "13-152", False, "Sectionalising switch SW-2"),
        ("SW-3", "switch", "18-135", False, "Sectionalising switch SW-3"),
        ("SW-4", "switch", "60-160", False, "Sectionalising switch SW-4"),
        ("SW-5", "switch", "97-197", False, "Sectionalising switch SW-5"),
    ]

    # Normally open tie switches
    # Sw7: connects bus 151 and bus 300
    # Sw8: connects bus 54 and bus 94
    # External tie: connects bus 250 to external East Grid
    f_ext_pos = _move(*buses.get("250", origin), 90, 250)
    buses["F_EXT"] = f_ext_pos

    switches.append(("Sw7", "tie", "151", "300", True, "Tie switch Sw7 (151-300)"))
    switches.append(("Sw8", "tie", "54", "94", True, "Tie switch Sw8 (54-94)"))
    switches.append(("TS-EXT", "tie", "250", "F_EXT", True, "Tie switch TS-EXT to East Grid"))

    return {
        "root": "150",
        "buses": buses,
        "sections": sections,
        "devices": devices,
        "switches": switches,
        "external_feeders": [
            {"bus": "F_EXT", "pos": f_ext_pos, "label": "East Grid (Feeder 2)"},
        ],
        "transformer_spacing": 65,
        "substation_label": "Pine Valley substation (bus 150)",
    }


_feeder: Feeder | None = None


def get_ieee123_feeder() -> Feeder:
    global _feeder
    if _feeder is None:
        _feeder = Feeder(ieee123_spec())
    return _feeder


def build_ieee123_database(path: Path | str, feeder: Feeder | None = None) -> None:
    """Build synthetic SQLite customer database for IEEE 123 feeder."""
    feeder = feeder or get_ieee123_feeder()
    rng = random.Random(SEED)
    con = create_database(Path(path))

    house_counter: dict[str, int] = {}
    used_accounts: set[str] = set()
    used_phones: set[str] = set()

    for sid, sec in feeder.sections.items():
        xfmrs = sorted((t for t in feeder.transformers.values() if t.section == sid), key=lambda t: t.offset_m)
        if not xfmrs:
            continue
        n = sum(rng.randint(8, 16) for _ in xfmrs)
        for i in range(n):
            offset = (i + 0.5) * sec.length_m / n
            side = 1 if i % 2 else -1
            lat, lon = feeder.point_on_section(sid, offset)
            lat, lon = _move(lat, lon, feeder.bearing_at(sid, offset) + 90 * side, rng.uniform(15, 40))
            nearest = min(xfmrs, key=lambda t: abs(t.offset_m - offset))
            house_counter[sec.street] = house_counter.get(sec.street, 100) + 2

            while (acct := f"{rng.randint(1_000_000_000, 9_999_999_999):010d}") in used_accounts:
                pass
            used_accounts.add(acct)

            while (phone := f"404{rng.randint(200, 999)}{rng.randint(1000, 9999):04d}") in used_phones:
                pass
            used_phones.add(phone)

            con.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,NULL)",
                (
                    acct,
                    f"{rng.choice(FIRST_NAMES)} {rng.choice(SURNAMES)}",
                    phone,
                    sec.street,
                    house_counter[sec.street],
                    nearest.id,
                    lat,
                    lon,
                ),
            )

    # Insert landmarks
    landmarks = [
        ("Pine Valley Community Hospital", ["hospital", "clinic", "medical center", "er"], "150r-149", 20.0, "hospital"),
        ("Pine Valley Water Pumping Station", ["water", "pumping station", "water works"], "13-152", 15.0, "water"),
        ("Pine Valley High School", ["school", "high school", "shelter"], "60-160", 25.0, "shelter"),
        ("Oakwood Shopping Plaza", ["plaza", "supermarket", "shops", "mall"], "97-197", 30.0, None),
    ]

    for name, aliases, sid, offset, critical in landmarks:
        if sid in feeder.sections:
            lat, lon = feeder.point_on_section(sid, offset)
            xfmrs = [t for t in feeder.transformers.values() if t.section == sid]
            nearest = min(xfmrs, key=lambda t: abs(t.offset_m - offset)) if xfmrs else next(iter(feeder.transformers.values()))
            con.execute(
                "INSERT INTO landmarks VALUES (?,?,?,?,?,?)",
                (name, "|".join(aliases), nearest.id, lat, lon, critical),
            )

    con.commit()
    con.close()
