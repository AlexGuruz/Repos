#!/usr/bin/env python3
"""
Build EXACT GPS route from NY DOT permit 3841749 turn-by-turn.
Uses BOTH columns from the permit: Route (road you're on) and To (instruction/next road).
One waypoint per permit row for precise mapping. OSRM returns full road geometry.

No API keys required. OSRM is public.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

# Full permit table: one row per PDF line. (miles, Route, To) → (lat, lon).
# Route = current road segment; To = instruction / next road. Waypoint at each transition.
PERMIT_ROWS = [
    (0.00, "Origin", "I-81; PA; Great Bend", 41.97686, -75.74225),
    (13.00, "I-81 NW", "Merge onto NY-17", 42.09870, -75.91800),
    (59.10, "NY-17 W", "Continue straight on I-86", 42.17745, -76.93345),   # NY-17/I-86 concurrency
    (81.10, "I-86 W", "Take Exit 30 toward NY-19/Belmont/Wellsville", 42.25620, -77.94890),
    (0.30, "I-86 Ramp SW", "Turn right onto NY-19", 42.25520, -77.94940),   # ramp end @ NY-19
    (17.90, "NY-19 NW", "Merge onto NY-19A [GENESEE ST]", 42.79590, -77.81700),
    (13.50, "NY-19A NE", "Merge onto NY-39", 42.97840, -77.93720),
    (7.30, "NY-39 N", "Turn left onto NY-246 [CENTER ST]", 42.97900, -77.93800),  # Le Roy NY-39/NY-246
    (10.50, "NY-246 N", "Turn left onto NY-63 [BIG TREE RD]", 43.00280, -78.20830),
    (9.20, "NY-63 NW", "Turn right onto BATAVIA STAFFORD TOWNLINE RD", 43.00650, -78.22200),
    (0.70, "BATAVIA STAFFORD TOWNLINE RD N", "Turn left onto NY-5 [MAIN RD]", 43.00800, -78.23500),
    (14.30, "NY-5 W", "Turn left onto NY-77 [ALLEGHANY RD]", 42.98580, -78.38920),
    (2.30, "NY-77 S", "Turn right onto NY-33 [MAIN ST]", 42.90060, -78.63920),
    (15.10, "NY-33 SW", "Turn right onto NY-78 [TRANSIT RD]", 42.96340, -78.75420),
    (2.90, "NY-78 N", "Turn left onto NY-78 Ramp [NY-324]", 42.98018, -78.80534),
    (0.10, "NY-78 Ramp SW", "Merge onto NY-324 Ramp", 42.98015, -78.81800),
    (0.00, "NY-324 Ramp S", "Turn right onto NY-324 [SHERIDAN DR]", 42.98012, -78.83000),
    (4.10, "NY-324 W", "Turn right onto I-290 Ramp", 42.98010, -78.85120),
    (0.40, "I-290 Ramp W", "Merge onto I-290", 42.98800, -78.86400),
    (2.10, "I-290 NW", "Take Exit 3 toward US-62/Niagara Falls Blvd", 42.99620, -78.87760),
    (0.30, "US-62 Ramp W", "Turn right onto US-62 [NIAGARA FALLS BLVD]", 42.99750, -78.87900),
    (4.00, "US-62 N", "Turn left onto NY-425 [ERIE AVE]", 43.03210, -78.88450),
    (1.20, "NY-425 SW", "Arrive at destination", 43.04834, -78.85371),
    (0.00, "Destination", "1070 Erie Ave, North Tonawanda 14120", 43.04834, -78.85371),
]

# Dedupe consecutive same coords so OSRM gets distinct waypoints (avoids zero-length segments).
def dedupe_waypoints(rows: list) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    last = (None, None)
    for r in rows:
        miles, route, to, lat, lon = r
        name = f"{route} → {to}"
        if (lat, lon) == last and len(out) > 0:
            continue
        last = (lat, lon)
        out.append((lat, lon, name))
    return out

USER_AGENT = "GigattPermitRoute/1.0"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"

# Build waypoint list from permit rows (deduped).
_waypoints_deduped = dedupe_waypoints(PERMIT_ROWS)
PERMIT_WAYPOINTS = [(lat, lon) for lat, lon, _ in _waypoints_deduped]
WAYPOINT_NAMES = [name for _, _, name in _waypoints_deduped]


def osrm_route(coords: list[tuple[float, float]]) -> list[tuple[float, float]] | None:
    """Return full route geometry as list of (lat, lon). OSRM uses lon,lat."""
    if len(coords) < 2:
        return None
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"{OSRM_URL}/{coord_str}?overview=full&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())
        if data.get("code") != "Ok" or not data.get("routes"):
            print("OSRM error:", data.get("code"), data.get("message", ""))
            return None
        geom = data["routes"][0]["geometry"]
        if geom["type"] != "LineString":
            return None
        return [(lat, lon) for lon, lat in geom["coordinates"]]
    except Exception as e:
        print("OSRM failed:", e)
        return None


def write_gpx_track(path: Path, coords: list[tuple[float, float]], names: list[str]) -> None:
    """GPX with <rte> waypoints for reference."""
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gpx version="1.1" creator="Gigatt Permit 3841749 EXACT" xmlns="http://www.topografix.com/GPX/1/1">\n')
        f.write('  <rte>\n')
        f.write('    <name>Tom NY Permit 3841749 - Exact turn-by-turn</name>\n')
        for i, (lat, lon) in enumerate(coords):
            name = names[i] if i < len(names) else f"Waypoint {i+1}"
            name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            f.write(f'    <rtept lat="{lat}" lon="{lon}"><name>{name}</name></rtept>\n')
        f.write("  </rte>\n")
        f.write("</gpx>\n")
    print(f"Wrote {len(coords)} waypoints to {path}")


def write_gpx_full_track(path: Path, track_points: list[tuple[float, float]]) -> None:
    """GPX with EXACT track (every point along the road). Use for follow-track navigation."""
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gpx version="1.1" creator="Gigatt Permit 3841749 EXACT TRACK" xmlns="http://www.topografix.com/GPX/1/1">\n')
        f.write('  <trk><name>Permit 3841749 Exact Route (follow this track)</name><trkseg>\n')
        for lat, lon in track_points:
            f.write(f'    <trkpt lat="{lat}" lon="{lon}"></trkpt>\n')
        f.write("  </trkseg></trk>\n")
        f.write("</gpx>\n")
    print(f"Wrote EXACT track ({len(track_points)} points) to {path}")


def main() -> None:
    base = Path(__file__).resolve().parent
    coords = PERMIT_WAYPOINTS
    print("Fetching EXACT road geometry from OSRM (permit waypoints)...")
    track = osrm_route(coords)
    if not track:
        print("OSRM failed. Using waypoints as track.")
        track = coords

    write_gpx_track(base / "Tom-NY-permit-route-exact-waypoints.gpx", coords, WAYPOINT_NAMES)
    write_gpx_full_track(base / "Tom-NY-permit-route-EXACT-TRACK.gpx", track)

    origin = f"{coords[0][0]},{coords[0][1]}"
    dest = f"{coords[-1][0]},{coords[-1][1]}"
    waypoints = "|".join(f"{lat},{lon}" for lat, lon in coords[1:-1])
    waypoints_enc = urllib.parse.quote(waypoints, safe="")
    url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={dest}&waypoints={waypoints_enc}&travelmode=driving"
    out_url = base / "Tom-NY-EXACT-Google-Maps-URL.txt"
    with open(out_url, "w", encoding="utf-8") as f:
        f.write(url)
    print(f"Google Maps URL saved to {out_url}")
    print("\nDone. Use Tom-NY-permit-route-EXACT-TRACK.gpx for exact turn-by-turn.")


if __name__ == "__main__":
    main()
