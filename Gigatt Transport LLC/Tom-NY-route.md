# Tom - NY Permit Route (Turn-by-Turn from PDF)

---

## EXACT GPS ROUTE (use these)

| File | Use |
|------|-----|
| **Tom-NY-permit-route-EXACT-TRACK.gpx** | **Exact route.** 6,776 points along the road from OSRM. Import into your GPS/nav app and **follow track** for turn-by-turn that matches the permit. |
| **Tom-NY-EXACT-Google-Maps-URL.txt** | Google Maps link with the same 15 waypoints (exact coordinates at each permit turn). Open for turn-by-turn in browser/app. |
| **Tom-NY-permit-route-exact-waypoints.gpx** | Same 15 waypoints as named route points (reference or for apps that prefer waypoints over track). |

**How it was built:** The route uses **both permit columns**: **Route** (road you’re on) and **To** (instruction/next road). There is one waypoint per permit row (23 waypoints), including ramps and merges (e.g. NY-78 Ramp → NY-324 Ramp → NY-324 [SHERIDAN DR]). OSRM returns the full road geometry between waypoints; that geometry is written as a GPX **track**.

**To re-build:** Run `python build_exact_permit_route.py` in this folder (no API keys needed).

---

**Permit:** 3841749 · **Origin:** I-81, Great Bend, PA · **Destination:** 1070 Erie Ave, North Tonawanda, NY 14120

## Turn-by-turn (exactly as PDF)

| Miles | Route | Instruction |
|------:|-------|-------------|
| 0.00 | Origin | I-81; PA; Great Bend |
| 13.00 | I-81 NW | Merge onto NY-17 |
| 59.10 | NY-17 W | Continue straight on I-86 |
| 81.10 | I-86 W | Take Exit 30 toward NY-19/Belmont/Wellsville |
| 0.30 | I-86 Ramp SW | Turn right onto NY-19 |
| 17.90 | NY-19 NW | Merge onto NY-19A [GENESEE ST] |
| 13.50 | NY-19A NE | Merge onto NY-39 |
| 7.30 | NY-39 N | Turn left onto NY-246 [CENTER ST] |
| 10.50 | NY-246 N | Turn left onto NY-63 [BIG TREE RD] |
| 9.20 | NY-63 NW | Turn right onto BATAVIA STAFFORD TOWNLINE RD |
| 0.70 | BATAVIA STAFFORD TOWNLINE RD N | Turn left onto NY-5 [MAIN RD] |
| 14.30 | NY-5 W | Turn left onto NY-77 [ALLEGHANY RD] |
| 2.30 | NY-77 S | Turn right onto NY-33 [MAIN ST] |
| 15.10 | NY-33 SW | Turn right onto NY-78 [TRANSIT RD] |
| 2.90 | NY-78 N | Turn left onto NY-78 Ramp [NY-324] |
| 0.10 | NY-78 Ramp SW | Merge onto NY-324 Ramp |
| 0.00 | NY-324 Ramp S | Turn right onto NY-324 [SHERIDAN DR] |
| 4.10 | NY-324 W | Turn right onto I-290 Ramp |
| 0.40 | I-290 Ramp W | Merge onto I-290 |
| 2.10 | I-290 NW | Take Exit 3 toward US-62/Niagara Falls Blvd |
| 0.30 | US-62 Ramp W | Turn right onto US-62 [NIAGARA FALLS BLVD] |
| 4.00 | US-62 N | Turn left onto NY-425 [ERIE AVE] |
| 1.20 | NY-425 SW | Arrive at destination |
| 0.00 | Destination | 1070 Erie Ave, North Tonawanda 14120 |

**Total distance (per permit):** 259.40 miles

---

## 1. GPX file (for turn-by-turn GPS / nav apps)

**File:** `Tom-NY-permit-route.gpx` (in this folder)

- **Use it in:** Garmin, CoPilot, TruckMap, Sygic, Google Earth, or any app that imports GPX routes.
- **What it is:** A route with **15 waypoints** at each permit turn (coordinates). Load the file → start navigation → the app will give turn-by-turn along this path.
- **How to load:** Email yourself the .gpx or put it on a USB; open it from your nav app’s “Import route” / “Load GPX” (varies by app). On phone, “Open with” a maps/GPX app.

---

## 2. Google Maps link (turn-by-turn in browser / Google Maps app)

This link uses **coordinates** for origin, destination, and every waypoint so the route follows the permit and Google gives turn-by-turn.

**Open this link on your phone or computer:**

**https://www.google.com/maps/dir/?api=1&origin=41.9733,-75.7444&destination=43.0483,-78.8539&waypoints=42.0987,-75.9180%7C42.2562,-77.9489%7C42.7959,-77.8170%7C42.9784,-77.9372%7C43.0028,-78.2083%7C43.0080,-78.2350%7C42.9858,-78.3892%7C42.9006,-78.6392%7C42.9634,-78.7542%7C42.9845,-78.8010%7C42.9801,-78.8512%7C42.9962,-78.8776%7C43.0321,-78.8845&travelmode=driving**

- On **phone:** Open in Chrome or the Google Maps app → tap “Directions” / “Start” for turn-by-turn.
- **Waypoints** = permit turns in order (I-81→NY-17→I-86→Exit 30→NY-19→…→1070 Erie Ave).

---

### Copy-paste Google Maps URL

```
https://www.google.com/maps/dir/?api=1&origin=41.9733,-75.7444&destination=43.0483,-78.8539&waypoints=42.0987,-75.9180%7C42.2562,-77.9489%7C42.7959,-77.8170%7C42.9784,-77.9372%7C43.0028,-78.2083%7C43.0080,-78.2350%7C42.9858,-78.3892%7C42.9006,-78.6392%7C42.9634,-78.7542%7C42.9845,-78.8010%7C42.9801,-78.8512%7C42.9962,-78.8776%7C43.0321,-78.8845&travelmode=driving
```

---

### Waypoint list (matches permit turn-by-turn)

| # | Permit step | Coordinates (lat,lon) |
|---|-------------|------------------------|
| 1 | Origin: I-81 Great Bend, PA | 41.9733, -75.7444 |
| 2 | I-81 → Merge NY-17 (I-86) | 42.0987, -75.9180 |
| 3 | I-86 Exit 30 → NY-19 | 42.2562, -77.9489 |
| 4 | NY-19 → NY-19A (Genesee St) | 42.7959, -77.8170 |
| 5 | NY-19A → NY-39 → NY-246 | 42.9784, -77.9372 |
| 6 | NY-246 → NY-63 (Big Tree Rd) | 43.0028, -78.2083 |
| 7 | NY-63 → Batavia Stafford Townline → NY-5 | 43.0080, -78.2350 |
| 8 | NY-5 → NY-77 (Alleghany Rd) | 42.9858, -78.3892 |
| 9 | NY-77 → NY-33 (Main St) | 42.9006, -78.6392 |
| 10 | NY-33 → NY-78 (Transit Rd) | 42.9634, -78.7542 |
| 11 | NY-78 → NY-324 (Sheridan Dr) | 42.9845, -78.8010 |
| 12 | NY-324 → I-290 | 42.9801, -78.8512 |
| 13 | I-290 Exit 3 → US-62 | 42.9962, -78.8776 |
| 14 | US-62 → NY-425 (Erie Ave) | 43.0321, -78.8845 |
| 15 | Destination: 1070 Erie Ave, North Tonawanda | 43.0483, -78.8539 |

---

**For permit compliance:** Always follow the official turn-by-turn on the NY DOT permit; use the GPX and Google link for GPS turn-by-turn along the same route.
