"""Light stemmer ``ar-light-1`` for normalised Arabic tokens.

Known limitation, carried from IR1.1 and tracked as a risk: broken plurals are not reduced to their singular.
"""
from __future__ import annotations

import re

STEMMER_VERSION = "ar-light-1"

_PREFIXES = ("ولل", "فلل", "وال", "بال", "كال", "فال", "لل", "ال", "و")
_SUFFIXES = ("ها", "ان", "ات", "ون", "ين", "يه", "ه", "ي")  # after normalisation ta marbuta is already "ه"
_ARABIC = re.compile("^[ء-ي]+$")
_WORD = re.compile(r"\w+")
_MIN_STEM = 3


def light_stem(token: str) -> str:
    """Strip at most one prefix, then suffixes repeatedly, never leaving fewer than three letters."""
    if not _ARABIC.match(token):
        return token
    for prefix in _PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= _MIN_STEM:
            token = token[len(prefix):]
            break
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM:
                token = token[: -len(suffix)]
                changed = True
                break
    return token


def stem_text(normalised: str) -> str:
    """Stem every word of already-normalised text; the result is what the stem column indexes."""
    return " ".join(light_stem(word) for word in _WORD.findall(normalised))
