#!/usr/bin/env python3
"""
Verify Tom NY Permit 3841749 route: compare OSRM leg distances to permit segment miles.
Run after build_exact_permit_route.py. Helps confirm waypoints match the permit.
"""
import json
import urllib.request
from pathlib import Path

# Import waypoints from build script
import build_exact_permit_route as b

PERMIT_TOTAL_MILES = 259.40

def main():
    # Permit segment miles (from PDF: cumulative miles at each row, so segment = diff)
    cumulative = [0.00, 13.00, 59.10, 81.10, 81.40, 99.30, 112.80, 120.10, 130.60, 139.80, 140.50, 154.80, 157.10, 172.20, 175.10, 175.20, 175.20, 179.30, 179.70, 181.80, 182.10, 186.10, 187.30, 187.30]
    permit_segment_miles = [round(cumulative[i+1] - cumulative[i], 2) for i in range(len(cumulative)-1)]
    # We have 23 waypoints → 22 legs. Permit has 23 segment lengths (0.00 origin to 0.00 dest). So 22 segments between waypoints.
    # Deduped waypoints may drop some rows; use same number of legs as OSRM returns.
    coords = b.PERMIT_WAYPOINTS
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"https://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": b.USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    if data.get("code") != "Ok" or not data.get("routes"):
        print("OSRM error:", data.get("code"))
        return
    route = data["routes"][0]
    legs = route.get("legs", [])
    total_osrm_m = route["distance"]
    total_osrm_mi = total_osrm_m / 1609.344
    print("=" * 60)
    print("ROUTE ACCURACY CHECK (Permit 3841749)")
    print("=" * 60)
    print(f"Permit total (PDF):     {PERMIT_TOTAL_MILES} miles")
    print(f"OSRM route total:       {total_osrm_mi:.2f} miles")
    print(f"Difference:             {total_osrm_mi - PERMIT_TOTAL_MILES:+.2f} miles")
    print()
    print("Leg-by-leg: Permit segment vs OSRM leg (big gaps = check waypoint)")
    print("-" * 60)
    names = b.WAYPOINT_NAMES
    for i, leg in enumerate(legs):
        leg_mi = leg["distance"] / 1609.344
        permit_mi = permit_segment_miles[i] if i < len(permit_segment_miles) else None
        label = (names[i][:45] if i < len(names) else f"Leg {i+1}").replace("\u2192", "->")
        if permit_mi is not None:
            diff = leg_mi - permit_mi
            flag = "  *** CHECK" if abs(diff) > 5 else ""
            print(f"  {label}: permit {permit_mi:.1f} mi  OSRM {leg_mi:.1f} mi  (diff {diff:+.1f}){flag}")
        else:
            print(f"  {label}: OSRM {leg_mi:.1f} mi")
    print("-" * 60)
    print("\nHow to verify in the field:")
    print("1. Open the Google Maps link from the email on your phone.")
    print("2. Tap Start and follow turn-by-turn.")
    print("3. Hold the permit PDF: at each instruction, confirm the road name")
    print("   and turn (Route column + To column) match the permit.")
    print("4. If any turn or road doesn't match, note the location and we can")
    print("   adjust that waypoint.")


if __name__ == "__main__":
    main()
