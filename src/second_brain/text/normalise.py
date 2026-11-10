"""Text normaliser ``ar-en-1``.

Engine-independent: the same function is applied to stored text before indexing and to queries.
Ported unchanged from the IR1.1 tokenizer probe; its recorded outputs are the test oracle.
"""
from __future__ import annotations

import re
import unicodedata

NORMALISER_VERSION = "ar-en-1"

_TASHKEEL = re.compile("[ً-ٰٟۖ-ۭ]")
# tatweel, zero-width and bidirectional controls, byte-order mark, Arabic letter mark
_CONTROLS = re.compile("[ـ​-‏‪-‮⁦-⁩﻿؜]")
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ک": "ك", "ی": "ي"})
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalise(text: str) -> str:
    """NFKC, strip tashkeel, tatweel and control characters, fold letter variants, map digits, casefold."""
    t = unicodedata.normalize("NFKC", text)
    t = _TASHKEEL.sub("", t)
    t = _CONTROLS.sub("", t)
    t = t.translate(_FOLD).translate(_DIGITS)
    return t.casefold()
