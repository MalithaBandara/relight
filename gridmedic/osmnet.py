"""Build a realistic radial feeder from real OpenStreetMap roads and buildings.

Distribution lines in suburbs run along the streets, so the feeder is a shortest-path
tree over the real road network, grown from a substation at the edge of the area.
Branch points become buses; reclosers go on the big branches, fuses on laterals, and
the largest recloser zone gets two remote sectionalising switches and a normally-open
tie to a neighbouring feeder (Feeder 2) at its far end. Customers are the real
buildings, each assigned to its nearest service transformer.

Only geometry and names come from OpenStreetMap; the electrical network, customers and
accounts are synthetic. Map data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import heapq
import json
import math
import random
from collections import Counter

from .config import DATA_DIR
from .customers import create_database
from .grid import Feeder, _move, bearing, haversine_m

MAJOR = {"primary": 0.6, "secondary": 0.7, "tertiary": 0.8, "residential": 1.0, "unclassified": 1.0,
         "living_street": 1.2}
LANDMARK_KIND = {"hospital": ("Hospital", "hospital"), "clinic": ("Clinic", None), "school": ("School", "shelter"),
                 "college": ("College", "shelter"), "place_of_worship": ("Place of worship", None),
                 "marketplace": ("Market", None), "fire_station": ("Fire station", "emergency"),
                 "police": ("Police station", "emergency"), "water_works": ("Water works", "water"),
                 "pumping_station": ("Pumping station", "water"), "water_tower": ("Water tower", "water")}


def load(area: str) -> dict:
    return json.loads((DATA_DIR / "osm" / f"{area}.json").read_text(encoding="utf-8"))


def _road_graph(data: dict, center: tuple[float, float], radius: float):
    pos: dict[int, tuple[float, float]] = {}
    adj: dict[int, dict[int, tuple[float, str, str]]] = {}
    for e in data["elements"]:
        t = e.get("tags", {})
        if e["type"] != "way" or "highway" not in t or "geometry" not in e:
            continue
        cls = t["highway"]
        name = t.get("name:en") or t.get("name") or ""
        pts = list(zip(e["nodes"], e["geometry"]))
        for (a, ga), (b, gb) in zip(pts, pts[1:]):
            pa, pb = (ga["lat"], ga["lon"]), (gb["lat"], gb["lon"])
            if haversine_m(pa, center) > radius or haversine_m(pb, center) > radius:
                continue
            pos[a], pos[b] = pa, pb
            d = haversine_m(pa, pb)
            adj.setdefault(a, {})[b] = (d, name, cls)
            adj.setdefault(b, {})[a] = (d, name, cls)
    # Keep the largest connected piece.
    seen, best = set(), []
    for start in adj:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            n = stack.pop()
            comp.append(n)
            for m in adj[n]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        if len(comp) > len(best):
            best = comp
    keep = set(best)
    return {n: pos[n] for n in keep}, {n: {m: v for m, v in adj[n].items() if m in keep} for n in keep}


def _pick_node(pos, adj, center, radius, bearing_deg, frac=0.85):
    """A node near the edge of the area in a given direction, preferring major roads."""
    target = _move(*center, bearing_deg, radius * frac)

    def cost(n):
        major = min(MAJOR.get(v[2], 1.2) for v in adj[n].values())
        return haversine_m(pos[n], target) * (0.6 + major)

    return min(pos, key=cost)


def build_spec(area: str, cfg: dict) -> dict:
    data = load(area)
    a = data["gridmedic_area"]
    center, radius = (a["lat"], a["lon"]), a["radius_m"]
    pos, adj = _road_graph(data, center, radius)
    root = _pick_node(pos, adj, center, radius, cfg.get("substation_bearing", 270))

    # Shortest-path tree from the substation; lines prefer the bigger roads.
    dist, parent = {root: 0.0}, {root: None}
    heap = [(0.0, root)]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist[n]:
            continue
        for m, (length, _, cls) in adj[n].items():
            nd = d + length * MAJOR.get(cls, 1.2)
            if nd < dist.get(m, math.inf):
                dist[m], parent[m] = nd, n
                heapq.heappush(heap, (nd, m))
    kids: dict[int, list[int]] = {}
    for n, p in parent.items():
        if p is not None:
            kids.setdefault(p, []).append(n)

    # Drop short dead-end spurs (driveways, stubs) that serve nobody.
    def spur_len(n):
        return sum(adj[n][c][0] + spur_len(c) for c in kids.get(n, []))
    for n in list(kids):
        kids[n] = [c for c in kids[n] if adj[n][c][0] + spur_len(c) >= cfg.get("min_spur_m", 40)]

    # Buses: the root, branch points, ends, name changes and every ~max_section_m along a chain.
    max_len = cfg.get("max_section_m", 450)
    bus_of: dict[int, str] = {}
    sections = []
    counter = iter(range(1, 10**6))

    def edge_name(p, c):
        return adj[p][c][1]

    stack = [(root, None)]
    bus_of[root] = "SUB"
    while stack:
        start, _ = stack.pop()
        for c in kids.get(start, []):
            path = [start, c]
            length = adj[start][c][0]
            names = Counter({edge_name(start, c): adj[start][c][0]})
            n = c
            while (len(kids.get(n, [])) == 1 and length < max_len
                   and edge_name(n, kids[n][0]) == edge_name(path[-2], n)):
                nxt = kids[n][0]
                length += adj[n][nxt][0]
                names[edge_name(n, nxt)] += adj[n][nxt][0]
                path.append(nxt)
                n = nxt
            if n not in bus_of:
                bus_of[n] = f"B{next(counter)}"
            street = names.most_common(1)[0][0] or cfg.get("unnamed", "Unnamed road")
            sections.append({"id": f"{bus_of[start]}-{bus_of[n]}", "from": bus_of[start], "to": bus_of[n],
                             "coords": [pos[x] for x in path], "street": street})
            stack.append((n, start))

    # Unnamed lanes take the name of the named road they branch from ("<road> Cross Street 2"), as locals
    # would describe them; a whole unnamed branch shares one name.
    unnamed = cfg.get("unnamed", "Unnamed road")
    by_to = {s["to"]: s for s in sections}
    orig = {s["id"]: s["street"] for s in sections}
    branch_name: dict[str, str] = {}
    count: dict[str, int] = {}
    for s in sections:
        if orig[s["id"]] != unnamed:
            continue
        top, p = s, by_to.get(s["from"])
        while p is not None and orig[p["id"]] == unnamed:
            top, p = p, by_to.get(p["from"])
        if p is None:
            continue
        if top["id"] not in branch_name:
            base = orig[p["id"]]
            count[base] = count.get(base, 0) + 1
            branch_name[top["id"]] = f"{base} Cross Street {count[base]}"
        s["street"] = branch_name[top["id"]]

    # A single breaker at the head of the feeder: if the substation node branches, add a stub.
    buses = {bus_of[n]: pos[n] for n in bus_of}
    root_children = [s for s in sections if s["from"] == "SUB"]
    if len(root_children) > 1:
        buses["S0"] = buses["SUB"]
        buses["SUB"] = _move(*buses["S0"], cfg.get("substation_bearing", 270), 25)
        for s in root_children:
            s["from"], s["id"] = "S0", s["id"].replace("SUB-", "S0-", 1)
        sections.insert(0, {"id": "SUB-S0", "from": "SUB", "to": "S0",
                            "coords": [buses["SUB"], buses["S0"]], "street": root_children[0]["street"]})

    spec = {"root": "SUB", "buses": buses, "sections": sections, "devices": [], "switches": [],
            "transformer_spacing": cfg.get("transformer_spacing", 100),
            "substation_label": cfg.get("substation_label", "Substation")}
    _place_devices(spec, cfg)
    return spec


def _place_devices(spec: dict, cfg: dict) -> None:
    """Breaker, reclosers on big branches, fuses on laterals, switches and a tie in the biggest zone."""
    secs = {s["id"]: s for s in spec["sections"]}
    children: dict[str, list[str]] = {}
    for s in spec["sections"]:
        children.setdefault(s["from"], []).append(s["id"])
    length = {sid: sum(haversine_m(a, b) for a, b in zip(s["coords"], s["coords"][1:])) for sid, s in secs.items()}
    below: dict[str, float] = {}
    depth: dict[str, int] = {}

    def total(sid, d=0):
        depth[sid] = d
        below[sid] = length[sid] + sum(total(c, d + 1) for c in children.get(secs[sid]["to"], []))
        return below[sid]

    head = children["SUB"][0]
    grand = total(head)

    def subtree(sid):
        out, st = [], [sid]
        while st:
            x = st.pop()
            out.append(x)
            st.extend(children.get(secs[x]["to"], []))
        return out

    spec["devices"].append(("BRK-1", "breaker", head, True, f"{spec['substation_label']} feeder breaker"))
    taken: set[str] = set()
    reclosers = []
    lo, hi = cfg.get("recloser_share", (0.12, 0.45))
    for sid in sorted(secs, key=lambda x: -below[x]):
        if len(reclosers) >= cfg.get("reclosers", 3) or sid == head or sid in taken:
            continue
        if lo <= below[sid] / grand <= hi and depth[sid] >= 2:
            reclosers.append(sid)
            taken |= set(subtree(sid))
            taken |= {p for p in secs if sid in subtree(p)}  # no recloser above another
    for i, sid in enumerate(reclosers, 1):
        spec["devices"].append((f"REC-{i}", "recloser", sid, True, f"{secs[sid]['street']} recloser"))

    fused: set[str] = set()
    n_fuse = 0
    for sid in sorted(secs, key=lambda x: depth[x]):
        parent_bus = secs[sid]["from"]
        if (sid in reclosers or sid == head or sid in fused or len(children.get(parent_bus, [])) < 2
                or below[sid] / grand > cfg.get("fuse_share", 0.08) or below[sid] < cfg.get("fuse_min_m", 150)):
            continue
        n_fuse += 1
        spec["devices"].append((f"FUS-{n_fuse}", "fuse", sid, False, f"{secs[sid]['street']} fuse"))
        fused |= set(subtree(sid))
        if n_fuse >= cfg.get("max_fuses", 30):
            break

    if not reclosers or not cfg.get("tie", True):
        return
    # Tie and sectionalising switches in the biggest recloser zone, along its longest path.
    zone = [s for s in subtree(reclosers[0]) if s not in fused]
    far = max(zone, key=lambda x: sum(length[y] for y in _path_up(secs, x, reclosers[0])))
    path = list(reversed(_path_up(secs, far, reclosers[0])))  # recloser section ... far section
    if len(path) >= 4:
        a, b = path[len(path) // 3], path[2 * len(path) // 3]
        spec["switches"] += [("SW-1", "switch", a, False, f"{secs[a]['street']} sectionalising switch"),
                             ("SW-2", "switch", b, False, f"{secs[b]['street']} sectionalising switch")]
    end_bus = secs[far]["to"]
    p0, p1 = spec["buses"][secs[far]["from"]], spec["buses"][end_bus]
    spec["feeder2"] = {"bus": "F2", "pos": _move(*p1, bearing(p0, p1), 220),
                       "label": cfg.get("feeder2_label", "Feeder 2")}
    spec["switches"].append(("TS-1", "tie", end_bus, True, "Tie switch to Feeder 2"))


def _path_up(secs: dict, sid: str, stop: str) -> list[str]:
    by_to = {s["to"]: s["id"] for s in secs.values()}
    out = [sid]
    while out[-1] != stop:
        out.append(by_to[secs[out[-1]]["from"]])
    return out


def build_customers(path, feeder: Feeder, area: str, cfg: dict, locale: dict) -> None:
    """Customers are the real buildings near the feeder, each fed by its nearest transformer."""
    data = load(area)
    rng = random.Random(cfg.get("seed", 7))
    con = create_database(path)
    grid: dict[tuple[int, int], list] = {}
    for t in feeder.transformers.values():
        grid.setdefault((round(t.lat * 400), round(t.lon * 400)), []).append(t)

    def nearest(lat, lon, max_m):
        cx, cy = round(lat * 400), round(lon * 400)
        cands = [t for dx in (-1, 0, 1) for dy in (-1, 0, 1) for t in grid.get((cx + dx, cy + dy), [])]
        best = min(cands, key=lambda t: haversine_m((lat, lon), (t.lat, t.lon)), default=None)
        if best and haversine_m((lat, lon), (best.lat, best.lon)) <= max_m:
            return best
        return None

    homes = []
    for e in data["elements"]:
        tags = e.get("tags", {})
        if "building" not in tags or "center" not in e:
            continue
        lat, lon = e["center"]["lat"], e["center"]["lon"]
        t = nearest(lat, lon, cfg.get("max_service_m", 120))
        if t is None or tags["building"] in ("garage", "garages", "shed", "roof", "carport"):
            continue
        multi = tags["building"] in ("apartments", "residential", "commercial", "yes") and rng.random() < cfg.get(
            "multi_unit_share", 0.0)
        units = rng.randint(*cfg.get("units_multi", (6, 20))) if multi else 1
        homes.append((t, lat, lon, units))

    # Number houses along each street in the order they sit along the line.
    by_street: dict[str, list] = {}
    for t, lat, lon, units in homes:
        by_street.setdefault(feeder.sections[t.section].street, []).append((t.offset_m, t, lat, lon, units))
    used_acct, used_phone = set(), set()
    for street, items in by_street.items():
        items.sort(key=lambda x: (x[1].section, x[0]))
        for i, (_, t, lat, lon, units) in enumerate(items):
            house = locale["house_no"](i)
            for u in range(units):
                while (acct := locale["account"](rng)) in used_acct:
                    pass
                used_acct.add(acct)
                while (phone := locale["phone"](rng)) in used_phone:
                    pass
                used_phone.add(phone)
                con.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,NULL)",
                            (acct, f"{rng.choice(locale['first'])} {rng.choice(locale['last'])}", phone, street,
                             house, t.id, lat + u * 1e-6, lon))

    n = 0
    for e in data["elements"]:
        tags = e.get("tags", {})
        kind = tags.get("amenity") or tags.get("man_made")
        if kind not in LANDMARK_KIND:
            continue
        c = e.get("center") or ({"lat": e["lat"], "lon": e["lon"]} if "lat" in e else None)
        if not c:
            continue
        t = nearest(c["lat"], c["lon"], 200)
        if t is None:
            continue
        label, critical = LANDMARK_KIND[kind]
        street = feeder.sections[t.section].street
        name = f"{label} on {street}"  # generic: the outage story is fictional, so no real names
        aliases = [label.lower(), kind.replace("_", " ")] + locale.get("aliases", {}).get(kind, [])
        con.execute("INSERT INTO landmarks VALUES (?,?,?,?,?,?)",
                    (name, "|".join(aliases), t.id, c["lat"], c["lon"], critical))
        if critical:
            n += 1
            con.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?)",
                        (f"9{n:09d}", name, f"{locale['facility_phone']}{n:04d}", street, 0, t.id,
                         c["lat"], c["lon"], critical))
    con.commit()
    con.close()
