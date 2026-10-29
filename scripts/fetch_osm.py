"""Download roads, buildings and landmarks for a scenario area from OpenStreetMap (Overpass API).

The result is cached in data/osm/<area>.json so scenarios build offline afterwards.
Map data (c) OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright

Usage:  python scripts/fetch_osm.py houston chennai
"""

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
AREAS = {
    # name: (lat, lon, radius_m)
    "houston": (29.7935, -95.4930, 1300),  # Spring Branch, Houston TX
    "chennai": (12.9790, 80.2190, 1500),  # Velachery, Chennai
}
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]


def query(lat: float, lon: float, r: int) -> str:
    a = f"(around:{r},{lat},{lon})"
    return f"""[out:json][timeout:240];
way["highway"~"^(primary|secondary|tertiary|residential|unclassified|living_street)$"]{a};
out geom;
way["building"]{a};
out center qt;
(
  nwr["amenity"~"^(hospital|clinic|school|college|place_of_worship|marketplace|fire_station|police)$"]{a};
  nwr["man_made"~"^(water_works|pumping_station|water_tower)$"]{a};
);
out center qt;"""


def main() -> None:
    out_dir = ROOT / "data" / "osm"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or list(AREAS):
        lat, lon, r = AREAS[name]
        for url in ENDPOINTS:
            try:
                resp = httpx.post(url, data={"data": query(lat, lon, r)}, timeout=300,
                                  headers={"User-Agent": "Relight-hackathon/0.1"})
                resp.raise_for_status()
                break
            except Exception as e:  # noqa: BLE001 - try the next mirror
                print(f"{name}: {url} failed: {e}")
        else:
            sys.exit(f"{name}: all Overpass endpoints failed")
        data = resp.json()
        data["relight_area"] = {"name": name, "lat": lat, "lon": lon, "radius_m": r}
        (out_dir / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
        kinds = {}
        for e in data["elements"]:
            t = e.get("tags", {})
            k = "road" if "highway" in t else "building" if "building" in t else "landmark"
            kinds[k] = kinds.get(k, 0) + 1
        print(f"{name}: {kinds}")


if __name__ == "__main__":
    main()
