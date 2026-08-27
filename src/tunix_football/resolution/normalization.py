from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^a-z0-9]+")
_TRANSLATION = str.maketrans({"ı": "i", "İ": "i"})


def normalize_name(value: str) -> str:
    """Normalize names for matching without changing canonical display values."""

    translated = value.translate(_TRANSLATION)
    decomposed = unicodedata.normalize("NFKD", translated)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    folded = without_marks.casefold()
    return " ".join(_NON_WORD.sub(" ", folded).split())
