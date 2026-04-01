"""
Free weather context via Open-Meteo (no API key). Used instead of Tavily/Serper for weather asks.

Env (optional):
  WEATHER_LAT, WEATHER_LON — fixed coordinates (skip geocoding)
  WEATHER_CITY — default city name when message has no location (default: Chicago)
  WEATHER_TEMP_UNIT — fahrenheit | celsius (default: fahrenheit)
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather interpretation codes (subset)
_WMO_LABELS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def extract_location_hint(message: str) -> str | None:
    """
    Parse a city/region from common phrasings: 'weather in Austin', 'forecast for Paris TX'.
    Returns None to fall back to WEATHER_CITY / lat-lon env.
    """
    if not message:
        return None
    m = re.search(
        r"\bweather\s+(?:in|for|at|near)\s+([a-zA-Z][a-zA-Z0-9\s,\.\-]{1,48}?)(?:\?|$|\.|,)",
        message.strip(),
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r"\b(?:forecast|temperature)\s+(?:in|for|at)\s+([a-zA-Z][a-zA-Z0-9\s,\.\-]{1,48}?)(?:\?|$|\.|,)",
        message.strip(),
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None


def _get_json(url: str, timeout_sec: float = 10.0) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-lab-command-center/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _resolve_coordinates(location_hint: str | None) -> tuple[float, float, str] | None:
    """Return (lat, lon, label) or None."""
    lat_s = (os.environ.get("WEATHER_LAT") or "").strip()
    lon_s = (os.environ.get("WEATHER_LON") or "").strip()
    if lat_s and lon_s:
        try:
            lat, lon = float(lat_s), float(lon_s)
            label = (os.environ.get("WEATHER_CITY") or "configured location").strip() or "configured location"
            return lat, lon, label
        except ValueError:
            pass

    city = (location_hint or "").strip() or (os.environ.get("WEATHER_CITY") or "Chicago").strip() or "Chicago"
    q = urllib.parse.urlencode({"name": city, "count": 1, "language": "en", "format": "json"})
    data = _get_json(f"{_GEOCODE_URL}?{q}")
    if not data:
        return None
    results = data.get("results") or []
    if not results:
        return None
    r0 = results[0]
    lat, lon = r0.get("latitude"), r0.get("longitude")
    if lat is None or lon is None:
        return None
    name = r0.get("name") or city
    admin = r0.get("admin1") or ""
    country = r0.get("country") or ""
    label = ", ".join(x for x in (name, admin, country) if x)
    return float(lat), float(lon), label


def fetch_weather_text(location_hint: str | None = None) -> str:
    """
    Fetch a short human-readable current-weather summary (Open-Meteo).
    Returns empty string on failure.
    """
    resolved = _resolve_coordinates(location_hint)
    if not resolved:
        return ""

    lat, lon, label = resolved
    unit = (os.environ.get("WEATHER_TEMP_UNIT") or "fahrenheit").strip().lower()
    if unit not in ("fahrenheit", "celsius"):
        unit = "fahrenheit"

    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "temperature_unit": unit,
        "wind_speed_unit": "mph",
    })
    data = _get_json(f"{_FORECAST_URL}?{params}")
    if not data:
        return ""

    cur = data.get("current") or {}
    temp = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    rh = cur.get("relative_humidity_2m")
    code = cur.get("weather_code")
    wind = cur.get("wind_speed_10m")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    wmo = _WMO_LABELS.get(code_i, f"weather code {code}") if code_i is not None else "unknown"

    deg = "°F" if unit == "fahrenheit" else "°C"
    parts = [
        f"Location: {label} ({lat:.2f}, {lon:.2f}).",
        f"Conditions: {wmo}.",
    ]
    if temp is not None:
        parts.append(f"Temperature: {temp}{deg}" + (f" (feels like {feels}{deg})" if feels is not None else "") + ".")
    if rh is not None:
        parts.append(f"Relative humidity: {rh}%.")
    if wind is not None:
        parts.append(f"Wind: {wind} mph.")
    parts.append("Source: Open-Meteo (free, no API key).")
    return " ".join(parts)


def get_weather_evidence_text(message: str) -> str:
    """For orchestrator fallback path: formatted block to append to evidence."""
    hint = extract_location_hint(message)
    text = fetch_weather_text(hint)
    if not text:
        return ""
    return f"\n\nCurrent weather (Open-Meteo, not web search):\n---\n{text}\n---"
