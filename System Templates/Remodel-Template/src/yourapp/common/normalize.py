"""
Text normalization utilities.

Generic text normalization functions useful for data processing pipelines.
"""
import re

_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9 ]+")


def normalize_description(raw: str) -> str:
    """
    Deterministic normalization for text descriptions.
    - lowercase
    - strip
    - collapse whitespace
    - drop punctuation
    
    Args:
        raw: Raw text to normalize
        
    Returns:
        Normalized text string
    """
    if raw is None:
        return ""
    s = raw.lower().strip()
    s = _PUNCT.sub(" ", s)
    s = _SPACE.sub(" ", s)
    return s.strip()
