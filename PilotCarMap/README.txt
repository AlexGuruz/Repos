PilotCar Loads Map
=================

Portable web app: poll email for PilotCar load alerts, geocode routes, and view them on a dark map with hot zones and a sidebar of route cards. Assign drivers from a dropdown; filter by time and driver.

Quick start
-----------
1. Copy config.json.example to config.json.
2. In config.json set:
   - google_api_key: Your Google Maps API key (Geocoding + Maps JavaScript enabled).
   - For email polling: imap_user, imap_password (and optionally imap_host, imap_port, imap_folder).
3. (Optional) Add driver names to data/drivers.json as a JSON array, e.g. ["Driver A", "Driver B"].
4. Run: start.bat
   - This starts the poller, the local server, and opens the browser to http://127.0.0.1:8080.
5. To run from a flash drive: copy the whole PilotCarMap folder to the drive; use relative paths (default). Ensure Python is installed on the target PC, or ship a portable Python.

Config (config.json)
--------------------
- google_api_key (required for map, geocoding, and driving routes): Create in Google Cloud Console, enable Geocoding API, Maps JavaScript API, and Directions API; restrict the key to http://localhost:*.
- poll_interval_sec: Seconds between email polls (default 120).
- imap_host, imap_port, imap_user, imap_password, imap_folder: IMAP settings for load-alert inbox. Leave user/password blank to skip email polling (you can still use the UI with manually added or existing data in data/routes.json).

API key and secrets
-------------------
Do not commit config.json. You can store the API key in a file under E:\secrets and point config.json to it, or paste the key into config.json and keep that file out of version control (.gitignore includes config.json).

Data files
---------
- data/routes.json: List of routes (written by poller, updated by UI when you assign a driver).
- data/drivers.json: List of driver names for the sidebar dropdown.
- data/geocode_cache.json: Geocoding cache (created automatically).

Run without email
-----------------
To only use the map and sidebar (no polling): leave imap_user and imap_password empty in config.json. You can still add routes manually to data/routes.json (see schema in the plan) or run the poller once with: python poller.py --once after configuring IMAP.
