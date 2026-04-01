"""
PilotCar Loads Map - Email poller.
Polls IMAP for "Load Alert" emails, parses route lines, geocodes via Google API, appends to data/routes.json.
Run in a loop (e.g. every poll_interval_sec) or once.
"""
import hashlib
import imaplib
import email
import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(ROOT, "config.json")
ROUTES_PATH = os.path.join(DATA_DIR, "routes.json")
CACHE_PATH = os.path.join(DATA_DIR, "geocode_cache.json")

# Route types: each entry is (display_name, list of substrings to match in email body, case-insensitive)
ROUTE_TYPE_MATCHES = [
    ("Lead", ["lead"]),
    ("Chase", ["chase"]),
    ("High Pole", ["high pole", "highpole", "high-pole"]),
    ("Survey", ["survey"]),
    ("Flagger", ["flagger"]),
]
# Pay pattern: $amount optional /day or /mile, optional (total), optional (Quick Pay)
PAY_PATTERN = re.compile(
    r"\$\s*[\d,]+(?:\.\d{2})?\s*(?:/\s*day|/\s*mile)?\s*(?:\(total\))?\s*(?:\(Quick Pay\))?",
    re.IGNORECASE,
)
DOT_PATTERN = re.compile(r"DOT:\s*(\d+)", re.IGNORECASE)
MC_PATTERN = re.compile(r"MC:\s*(\d+)", re.IGNORECASE)
ROUTED_MILES_PATTERN = re.compile(r"(\d+)\s*routed\s*miles?", re.IGNORECASE)
# Optional origin/destination detail (e.g. "Origin: 123 Main St, City, ST" or "Pickup: ...")
ORIGIN_DETAIL_PATTERN = re.compile(
    r"(?:origin|pickup|from):\s*(.+?)(?=\n|$)", re.IGNORECASE | re.DOTALL
)
DEST_DETAIL_PATTERN = re.compile(
    r"(?:destination|delivery|to):\s*(.+?)(?=\n|$)", re.IGNORECASE | re.DOTALL
)


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Resolve API key from file path if set
    key_path = raw.get("google_api_key_path")
    if key_path and os.path.isfile(key_path):
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                raw = dict(raw)
                raw["google_api_key"] = f.read().strip()
        except IOError:
            pass
    # Resolve IMAP credentials from file path if set (line1=password, line2=email)
    cred_path = raw.get("imap_credentials_path")
    if cred_path and os.path.isfile(cred_path):
        try:
            with open(cred_path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f.readlines() if ln.strip()]
            if len(lines) >= 2:
                raw = dict(raw)
                raw["imap_password"] = lines[0].replace(" ", "")
                raw["imap_user"] = lines[1]
            elif len(lines) == 1:
                raw = dict(raw)
                raw["imap_user"] = lines[0]
        except IOError:
            pass
    return raw


def load_json(path, default):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def geocode(address, api_key):
    """Return (lat, lng) or (None, None). Uses cache."""
    cache = load_json(CACHE_PATH, {})
    key = address.strip().lower()
    if key in cache:
        return cache[key]["lat"], cache[key]["lng"]
    if not api_key:
        return None, None
    url = "https://maps.googleapis.com/maps/api/geocode/json?address=" + urllib.parse.quote(address) + "&key=" + api_key
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "OK" and data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                lat, lng = loc["lat"], loc["lng"]
                cache[key] = {"lat": lat, "lng": lng}
                save_json(CACHE_PATH, cache)
                return lat, lng
    except Exception:
        pass
    return None, None


def parse_load_alert_body(body):
    """
    Parse email body for rough start/end (city, state). Accepts:
      - "City, ST, USA to City, ST, USA" or "City, ST to City, ST"
      - "City, ST, USA > City, ST, USA"
    """
    if not body:
        return None
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return None
    # Find a line that looks like origin-to-destination (to or >) with city/state (comma)
    route_line = None
    for ln in lines:
        if "," not in ln:
            continue
        if " to " in ln:
            parts = re.split(r"\s+to\s+", ln, maxsplit=1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                route_line = ln
                break
        if " > " in ln:
            parts = re.split(r"\s*>\s*", ln, maxsplit=1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                route_line = ln
                break
    if not route_line:
        return None
    # Split on " to " or " > "
    if " to " in route_line:
        parts = re.split(r"\s+to\s+", route_line, maxsplit=1)
    else:
        parts = re.split(r"\s*>\s*", route_line, maxsplit=1)
    if len(parts) != 2:
        return None
    origin, destination = parts[0].strip(), parts[1].strip()
    # Prefer city/state-style for geocoding: ensure we have something like "City, ST" or "City, ST, USA"
    if len(origin) < 3 or len(destination) < 3:
        return None

    # Company: only use first line if it looks like a company name (not a subject/header line)
    first = (lines[0] or "").strip()
    company = ""
    if first:
        fl = first.lower()
        if (
            " to " not in fl
            and " mi" not in fl
            and "routed" not in fl
            and "needed" not in fl
            and "credentials" not in fl
            and not re.match(r"^\d+\s", first)
            and len(first) < 80
        ):
            company = first

    miles = None
    routed_miles = None
    date_val = None
    phone = None
    phone_text_only = False
    for ln in lines:
        mi = re.match(r"(\d+)\s*mi", ln, re.I)
        if mi:
            miles = int(mi.group(1))
        if re.match(r"^\d{1,2}/\d{1,2}", ln):
            date_val = ln
        digits = re.sub(r"\D", "", ln)
        if len(digits) >= 10:
            phone = ln.strip()
            if "text only" in ln.lower():
                phone_text_only = True
    rm = ROUTED_MILES_PATTERN.search(body)
    if rm:
        routed_miles = int(rm.group(1))
    dot_match = DOT_PATTERN.search(body)
    dot = dot_match.group(1) if dot_match else None
    mc_match = MC_PATTERN.search(body)
    mc = mc_match.group(1) if mc_match else None
    pay_match = PAY_PATTERN.search(body)
    pay = pay_match.group(0).strip() if pay_match else None

    origin_detail = None
    dest_detail = None
    om = ORIGIN_DETAIL_PATTERN.search(body)
    if om:
        origin_detail = om.group(1).strip().split("\n")[0].strip()
    dm = DEST_DETAIL_PATTERN.search(body)
    if dm:
        dest_detail = dm.group(1).strip().split("\n")[0].strip()

    body_lower = body.lower()
    route_types = []
    for display_name, substrings in ROUTE_TYPE_MATCHES:
        for sub in substrings:
            if sub.lower() in body_lower:
                route_types.append(display_name)
                break

    return {
        "company": company,
        "origin": origin,
        "destination": destination,
        "origin_detail": origin_detail,
        "dest_detail": dest_detail,
        "miles": miles,
        "routed_miles": routed_miles,
        "date": date_val,
        "phone": phone,
        "phone_text_only": phone_text_only,
        "pay": pay,
        "dot": dot,
        "mc": mc,
        "chase": route_line,
        "route_types": route_types,
    }


def route_id(parsed):
    h = hashlib.sha256(
        (parsed.get("origin", "") + "|" + parsed.get("destination", "") + "|" + parsed.get("date", "")).encode()
    ).hexdigest()
    return h[:16]


def poll_once(config):
    api_key = config.get("google_api_key", "")
    host = config.get("imap_host", "imap.gmail.com")
    port = int(config.get("imap_port", 993))
    user = config.get("imap_user", "")
    password = config.get("imap_password", "")
    folder = config.get("imap_folder", "INBOX")
    # Restrict to specific senders; default to PilotCarLoads if not configured
    allowed_senders_cfg = config.get("allowed_senders") or ["team@pilotcarloads.com"]
    allowed_senders = {s.lower() for s in allowed_senders_cfg}

    if not user or not password:
        return  # Skip IMAP if not configured

    routes = load_json(ROUTES_PATH, [])
    existing_ids = {r.get("id") for r in routes if r.get("id")}

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select(folder)
        # Search for recent emails (last 7 days); adjust if needed
        _, msg_ids = conn.search(None, "ALL")
        id_list = msg_ids[0].split()
        # Process newest first, limit to last 500 so we grab more history
        to_process = id_list[-500:] if len(id_list) > 500 else id_list
        to_process.reverse()

        for mid in to_process:
            _, data = conn.fetch(mid, "(RFC822)")
            if not data or not data[0]:
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)
            from_hdr = (msg.get("From") or "").lower()
            if not any(s in from_hdr for s in allowed_senders):
                continue
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        except Exception:
                            body = ""
                        break
            else:
                try:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    body = ""
            parsed = parse_load_alert_body(body)
            if not parsed:
                continue
            rid = route_id(parsed)
            if rid in existing_ids:
                continue
            origin_geocode = (parsed.get("origin_detail") or parsed["origin"]).strip()
            dest_geocode = (parsed.get("dest_detail") or parsed["destination"]).strip()
            origin_lat, origin_lng = geocode(origin_geocode, api_key)
            dest_lat, dest_lng = geocode(dest_geocode, api_key)
            route = {
                "id": rid,
                "origin": parsed["origin"],
                "destination": parsed["destination"],
                "origin_detail": parsed.get("origin_detail"),
                "dest_detail": parsed.get("dest_detail"),
                "origin_lat": origin_lat,
                "origin_lng": origin_lng,
                "dest_lat": dest_lat,
                "dest_lng": dest_lng,
                "miles": parsed["miles"],
                "routed_miles": parsed.get("routed_miles"),
                "company": parsed["company"],
                "chase": parsed.get("chase", ""),
                "date": parsed.get("date", ""),
                "phone": parsed.get("phone", ""),
                "phone_text_only": parsed.get("phone_text_only", False),
                "pay": parsed.get("pay"),
                "dot": parsed.get("dot"),
                "mc": parsed.get("mc"),
                "route_types": parsed.get("route_types", []),
                "status": "new",
                "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            routes.append(route)
            existing_ids.add(rid)

        conn.close()
        conn.logout()
    except Exception as e:
        print("Poller IMAP error:", e)
        return

    save_json(ROUTES_PATH, routes)


def main():
    config = load_config()
    poll_interval = int(config.get("poll_interval_sec", 120))
    print("PilotCar poller: running every", poll_interval, "s (Ctrl+C to stop)")
    while True:
        poll_once(config)
        time.sleep(poll_interval)


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        poll_once(load_config())
        print("Done (once).")
    else:
        main()
