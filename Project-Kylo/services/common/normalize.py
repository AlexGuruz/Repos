import re

_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9 ]+")

def normalize_description(raw: str) -> str:
    """
    Deterministic normalization for transaction descriptions.
    - lowercase
    - strip
    - collapse whitespace
    - drop punctuation
    - drop common bank noise tokens (configurable later)
    """
    if raw is None:
        return ""
    s = raw.lower().strip()
    s = _PUNCT.sub(" ", s)
    s = _SPACE.sub(" ", s)
    # future: remove noise prefixes like 'pos purchase', digits tails, etc.
    return s.strip()
