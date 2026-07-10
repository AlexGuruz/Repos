"""
Deterministic bank transaction cleaner — no LLM on the write path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

STATE_MAP: dict[str, str] = {
    "oklahoma": "OK",
    "ok": "OK",
    "texas": "TX",
    "tx": "TX",
    "missouri": "MO",
    "mo": "MO",
    "arkansas": "AR",
    "ar": "AR",
    "kansas": "KS",
    "ks": "KS",
    "indiana": "IN",
    "in": "IN",
    "wisconsin": "WI",
    "wi": "WI",
    "wyoming": "WY",
    "wy": "WY",
    "montana": "MT",
    "mt": "MT",
    "south dakota": "SD",
    "sd": "SD",
    "illinois": "IL",
    "il": "IL",
    "iowa": "IA",
    "ia": "IA",
    "california": "CA",
    "ca": "CA",
    "ohio": "OH",
    "oh": "OH",
    "michigan": "MI",
    "mi": "MI",
    "colorado": "CO",
    "co": "CO",
    "utah": "UT",
    "ut": "UT",
    "new mexico": "NM",
    "nm": "NM",
    "alabama": "AL",
    "al": "AL",
    "new york": "NY",
    "ny": "NY",
    "virginia": "VA",
    "va": "VA",
    "tennessee": "TN",
    "tn": "TN",
    "south carolina": "SC",
    "sc": "SC",
    "nebraska": "NE",
    "ne": "NE",
    "new jersey": "NJ",
    "nj": "NJ",
}

CITY_MAP: dict[str, str] = {
    "pauls v": "Pauls Valley",
    "pauls valley": "Pauls Valley",
    "poplar bluff": "Poplar Bluff",
    "van buren": "Van Buren",
    "paragould": "Paragould",
    "ardmore": "Ardmore",
    "purcell": "Purcell",
    "blacksburg": "Blacksburg",
}

FORMULA_PREFIXES = ("=", "=LET(", "=ARRAYFORMULA(", "=REGEX")

STATE_ABBRS = (
    "OK", "TX", "MO", "AR", "KS", "IN", "WI", "WY", "MT", "SD", "IL", "IA",
    "CA", "OH", "MI", "CO", "UT", "NM", "AL", "NY", "VA", "TN", "SC", "NE", "NJ",
)

_POS_PURCHASE_CITY = re.compile(
    r"(?i)(?:pos purchase|purchase)\s+"
    r"(?P<state>ok|tx|mo|ar|ks|in|wi|ca|oh|sc|ny)\s+"
    r"(?P<city>[a-z]+(?:\s+[a-z]+)*)",
)

_LOCATION_CITY_STATE = re.compile(
    r"(?P<city>[A-Za-z]+(?:\s+[A-Za-z]+)*)\s+"
    r"(?P<state>OK|TX|MO|AR|KS|IN|WI|WY|MT|SD|IL|IA|CA|OH|MI|CO|UT|NM|AL|NY|VA|TN|SC|NE|NJ)\b",
    re.I,
)

_LOCATION_CITY_STATE_NAME = re.compile(
    r"(?P<city>[A-Za-z]+(?:\s+[A-Za-z]+)*)\s+"
    r"(?P<state_name>Oklahoma|Texas|Missouri|Arkansas|Kansas|Indiana|Wisconsin|"
    r"Wyoming|Montana|South Dakota|Illinois|Iowa|California|Ohio|Michigan|"
    r"Colorado|Utah|New Mexico|Alabama|New York|Virginia|Tennessee|"
    r"South Carolina|Nebraska|New Jersey)\b",
    re.I,
)

_INVALID_CITY_WORDS = frozenset({
    "pos", "recur", "payment", "purchase", "atm", "online", "internet",
    "deposit", "transfer", "withdrawal", "reverse", "charge", "funds",
    "seq", "inside", "outside", "mobile", "consumer", "loan", "card",
})

CANONICAL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(wal-?mart|wm supercenter us)", re.I), "Walmart"),
    (re.compile(r"(murphy7440atwalmart|murphy7440atwalm|\bmurphy\b)", re.I), "Murphy"),
    (re.compile(r"spotify", re.I), "Spotify"),
    (re.compile(r"super 8", re.I), "Super 8"),
    (re.compile(r"maverik", re.I), "Maverik"),
    (re.compile(r"gas\s*&\s*dash", re.I), "Gas & Dash"),
    (re.compile(r"kroger fuel", re.I), "Kroger Fuel"),
    (re.compile(r"(py \*hteao|\bhteao\b)", re.I), "HTeaO"),
    (re.compile(r"(^qt\b|\bqt\s+\d+)", re.I), "QT"),
    (re.compile(r"the wooden spoon", re.I), "Wooden Spoon"),
    (re.compile(r"citi.*payment|citi card online payment", re.I), "Citi Payment"),
    (re.compile(r"capital one.*pmt|capital one.*payment", re.I), "Capital One"),
    (re.compile(r"consumer loans|payment to consumer loans", re.I), "Consumer Loan"),
    (re.compile(r"debit plus rewards|reverse charge", re.I), "Debit Rewards Reversal"),
    (re.compile(r"^deposit$|deposit@mobile|atm deposit|cash deposit", re.I), "Cash Deposit"),
    (re.compile(r"atm withdrawal", re.I), "ATM Withdrawal"),
    (
        re.compile(
            r"online transfer from chk|internet transfer from acct|funds transfer cr|\btransfer in\b|usaa funds transfer cr",
            re.I,
        ),
        "Transfer In",
    ),
    (
        re.compile(
            r"internet transfer to acct|funds transfer db|\btransfer out\b|usaa funds transfer db",
            re.I,
        ),
        "Transfer Out",
    ),
    (re.compile(r"kraken", re.I), "Kraken"),
    (re.compile(r"etoro|etoro viatrustly", re.I), "eToro"),
    (re.compile(r"coinbase", re.I), "Coinbase"),
    (re.compile(r"okgov|ok gov", re.I), "OK Gov"),
    (re.compile(r"omma license", re.I), "OMMA License"),
    (re.compile(r"city of purcell utilities", re.I), "City of Purcell Utilities"),
    (re.compile(r"amazon", re.I), "Amazon"),
]

TITLE_CASE_PRESERVE = {"eToro", "HTeaO", "OK Gov", "OMMA License", "QT", "Gas & Dash", "Kroger Fuel"}

FIXED_EVENT_LABELS = frozenset({
    "Cash Deposit",
    "Transfer In",
    "Transfer Out",
    "ATM Withdrawal",
    "Citi Payment",
    "Capital One",
    "Consumer Loan",
    "Debit Rewards Reversal",
})

LabelSource = str  # blank | alias | rule | fallback


@dataclass(frozen=True)
class AliasEntry:
    canonical_label: str
    city: str
    state: str


@dataclass(frozen=True)
class ProcessedRow:
    label: str
    location: str


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    s = re.sub(r"[\t\r]+", " ", s)
    return re.sub(r"\s+", " ", s)


def to_title_case(value: str) -> str:
    if value in TITLE_CASE_PRESERVE:
        return value
    return " ".join(word.capitalize() for word in value.split())


def build_alias_lookup(alias_map: dict[str, Any]) -> tuple[dict[str, AliasEntry], dict[str, AliasEntry]]:
    """Exact raw lookup + canonical-label default location lookup."""
    by_raw: dict[str, AliasEntry] = {}
    by_canonical: dict[str, AliasEntry] = {}
    for alias in alias_map.get("aliases", []):
        if not isinstance(alias, dict):
            continue
        canonical = str(alias.get("canonical_label") or "")
        city = str(alias.get("city") or "")
        state = str(alias.get("state") or "")
        entry = AliasEntry(canonical_label=canonical, city=city, state=state)
        if canonical and canonical not in by_canonical:
            if city or state:
                by_canonical[canonical] = entry
        for raw in alias.get("raw_inputs", []):
            key = normalize_text(str(raw)).lower()
            if key:
                by_raw[key] = entry
    return by_raw, by_canonical


def apply_replacements(text: str, rules: dict[str, Any] | None) -> str:
    if not rules:
        return text
    norm = rules.get("normalization") or {}
    for item in norm.get("replacements") or []:
        if not isinstance(item, dict):
            continue
        src = str(item.get("from") or "")
        dst = str(item.get("to") or "")
        if not src:
            continue
        flags = 0 if item.get("case_sensitive") else re.I
        text = re.sub(re.escape(src), dst, text, flags=flags)
    return text


def deterministic_fallback(raw: str) -> str:
    text = raw
    text = re.sub(
        r"(?i)pos purchase|recur payment|online payment|internet payment|payment to|reverse charge:?",
        "",
        text,
    )
    text = re.sub(r"(?i)seq#\s*\S+", "", text)
    text = re.sub(r"\b\d{2,}\b", "", text)
    text = re.sub(
        r"(?i)\b(ok|tx|mo|ar|ks|in|wi|wy|mt|sd|il|ia|ca|oh|mi|co|ut|nm|al|ny|va|tn|sc|ne|nj)\b.*$",
        "",
        text,
    )
    text = normalize_text(text)
    if not text:
        return "Unknown Merchant"
    return to_title_case(text[:64].strip())


def get_label_with_source(
    raw: str,
    alias_by_raw: dict[str, AliasEntry],
    *,
    cleaning_rules: dict[str, Any] | None = None,
) -> tuple[str, LabelSource]:
    """Return (label, source) where source is blank|alias|rule|fallback."""
    raw_norm = normalize_text(raw)
    if raw_norm == "":
        return "", "blank"

    prepared = apply_replacements(raw_norm, cleaning_rules)
    lower_raw = prepared.lower()
    if lower_raw in alias_by_raw:
        return alias_by_raw[lower_raw].canonical_label, "alias"

    for pattern, output in CANONICAL_RULES:
        if pattern.search(prepared):
            return output, "rule"

    return deterministic_fallback(prepared), "fallback"


def clean_label(
    raw: str,
    alias_by_raw: dict[str, AliasEntry],
    *,
    cleaning_rules: dict[str, Any] | None = None,
) -> str:
    label, _ = get_label_with_source(raw, alias_by_raw, cleaning_rules=cleaning_rules)
    return label


def is_fixed_event_label(label: str) -> bool:
    return label in FIXED_EVENT_LABELS


def normalize_state(state: str) -> str:
    key = normalize_text(state).lower()
    if key in STATE_MAP:
        return STATE_MAP[key]
    upper = state.strip().upper()
    if len(upper) == 2 and upper in STATE_ABBRS:
        return upper
    return ""


def _trim_city_tail(city: str) -> str:
    lower = city.lower()
    cut_markers = (
        " wm", " wal", " seq", " murphy", " supercenter", " #", " py ", " qt ",
        " inside", " outside", " motels", " fuel", " license",
    )
    end = len(city)
    for marker in cut_markers:
        idx = lower.find(marker)
        if idx > 0:
            end = min(end, idx)
    trimmed = city[:end].strip()
    return trimmed.split("  ")[0].strip()


def normalize_city(city: str) -> str:
    city = _trim_city_tail(city)
    key = normalize_text(city).lower()
    if key in CITY_MAP:
        return CITY_MAP[key]
    return to_title_case(city)


def format_location(city: str, state: str) -> str:
    city = normalize_city(city) if city else ""
    state = normalize_state(state) if state else ""
    if city and state:
        return f"{city}, {state}"
    if state:
        return state
    return ""


def _city_appears_in_raw(city: str, raw: str) -> bool:
    if not city:
        return False
    lower_raw = raw.lower()
    if city.lower() in lower_raw:
        return True
    for key, full in CITY_MAP.items():
        if full.lower() == city.lower() and key in lower_raw:
            return True
    return False


def _valid_city_name(city: str) -> bool:
    if not city or not normalize_text(city):
        return False
    words = normalize_text(city).lower().split()
    if any(w in _INVALID_CITY_WORDS for w in words):
        return False
    if len(words) >= 2 and words[0] in _INVALID_CITY_WORDS:
        return False
    return True


def _location_from_alias_entry(entry: AliasEntry, raw: str = "") -> str:
    if raw and entry.city and entry.state:
        phone_like = re.search(r"\d{3}[-.]?\d{3,}", raw)
        if phone_like and not _city_appears_in_raw(entry.city, raw):
            return entry.state
    return format_location(entry.city, entry.state)


def _scan_lone_state(raw: str) -> str:
    lower = raw.lower()
    recur_payment = re.search(
        r"(?i)(?:recur\s+)?payment\s+(OK|TX|MO|AR|KS|IN|WI|CA|OH|SC|NY)\b",
        raw,
    )
    if recur_payment:
        return recur_payment.group(1).upper()
    for abbr in STATE_ABBRS:
        if re.search(rf"(?i)(?:payment|purchase|recur)\s+{abbr}\b", raw):
            return abbr
        if re.search(rf"(?i)\b{abbr}\b(?:\s+\d|\s+\*|\s+seq#|$)", raw):
            return abbr
    if " tx" in lower or raw.upper().endswith(" TX"):
        return "TX"
    if " ok" in lower:
        return "OK"
    if " mo" in lower:
        return "MO"
    if " ar" in lower:
        return "AR"
    return ""


def extract_city_state(
    raw: str,
    alias_by_raw: dict[str, AliasEntry],
    alias_by_canonical: dict[str, AliasEntry],
    *,
    canonical_label: str | None = None,
) -> str:
    raw_norm = normalize_text(raw)
    if raw_norm == "":
        return ""

    lower_raw = raw_norm.lower()
    if lower_raw in alias_by_raw:
        loc = _location_from_alias_entry(alias_by_raw[lower_raw], raw_norm)
        if loc:
            return loc

    pos_match = _POS_PURCHASE_CITY.search(raw_norm)
    if pos_match:
        city = normalize_city(pos_match.group("city") or "")
        state = normalize_state(pos_match.group("state") or "")
        loc = format_location(city, state)
        if loc:
            return loc

    best: tuple[int, str] = (-1, "")
    for pattern in (_LOCATION_CITY_STATE, _LOCATION_CITY_STATE_NAME):
        for match in pattern.finditer(raw_norm):
            city = match.groupdict().get("city") or ""
            state = match.groupdict().get("state") or ""
            state_name = match.groupdict().get("state_name") or ""
            if state_name:
                state = normalize_state(state_name)
            else:
                state = normalize_state(state)
            city = normalize_city(city) if city else ""
            if city and not _valid_city_name(city):
                if state:
                    loc = state
                else:
                    continue
            else:
                loc = format_location(city, state)
            if loc and match.start() > best[0]:
                best = (match.start(), loc)

    if best[1]:
        return best[1]

    label = canonical_label or clean_label(raw_norm, alias_by_raw)
    if label in alias_by_canonical:
        loc = _location_from_alias_entry(alias_by_canonical[label], raw_norm)
        if loc:
            return loc

    return _scan_lone_state(raw_norm)


def process_transaction(
    raw: str,
    alias_by_raw: dict[str, AliasEntry],
    alias_by_canonical: dict[str, AliasEntry],
    *,
    cleaning_rules: dict[str, Any] | None = None,
) -> ProcessedRow:
    raw_norm = normalize_text(raw)
    if raw_norm == "":
        return ProcessedRow(label="", location="")
    label = clean_label(raw_norm, alias_by_raw, cleaning_rules=cleaning_rules)
    location = extract_city_state(
        raw_norm,
        alias_by_raw,
        alias_by_canonical,
        canonical_label=label,
    )
    return ProcessedRow(label=label, location=location)


def find_last_nonblank_row(values: list[str], start_row: int) -> int:
    last = start_row - 1
    for idx, val in enumerate(values, start=start_row):
        if normalize_text(val) != "":
            last = idx
    return last


def process_rows(
    source_values: list[str],
    start_row: int,
    alias_map: dict[str, Any],
    *,
    cleaning_rules: dict[str, Any] | None = None,
) -> tuple[list[ProcessedRow], int]:
    alias_by_raw, alias_by_canonical = build_alias_lookup(alias_map)
    last_row = find_last_nonblank_row(source_values, start_row)
    active_len = max(0, last_row - start_row + 1)
    active_values = source_values[:active_len]

    rows: list[ProcessedRow] = []
    for raw in active_values:
        rows.append(
            process_transaction(
                raw,
                alias_by_raw,
                alias_by_canonical,
                cleaning_rules=cleaning_rules,
            )
        )
    return rows, last_row


def assert_plain_values(values: list[str]) -> None:
    for value in values:
        text = str(value)
        if any(text.startswith(prefix) for prefix in FORMULA_PREFIXES):
            raise ValueError(f"Formula-like output detected: {value}")
