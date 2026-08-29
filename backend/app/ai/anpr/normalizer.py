"""Number-plate text normalisation & validation (India-focused, configurable).

Raw OCR is preserved separately; normalisation is transparent and position-aware
(only coercing ambiguous characters where the expected plate grammar makes the
correction unambiguous), never a blind rewrite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Standard Indian format:  SS  DD  L(1-3)  NNNN   e.g. GJ01AB1234
IND_STANDARD = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$")
# Bharat (BH) series:      DD  BH  NNNN  L(1-2)  e.g. 22BH1234AA
IND_BH = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")

PATTERNS = {"IN": [IND_STANDARD, IND_BH]}

# Ambiguous OCR confusions, resolved by expected character kind at a position.
_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "T": "7"}
_TO_ALPHA = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G", "4": "A"}


@dataclass
class NormalizedPlate:
    raw: str
    normalized: str
    valid_format: bool
    country: str = "IN"


def _clean(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _coerce_indian_standard(s: str) -> str | None:
    """Try to fit a cleaned string to SS DD L NNNN using position-aware fixes."""
    if not (9 <= len(s) <= 10):
        return None
    n = len(s)
    # layout: 2 alpha | 2 digit | (n-8) alpha | 4 digit    (for n=10)
    #         2 alpha | 1 digit | (n-7) alpha | 4 digit    (for n=9)
    digits_mid = 2 if n == 10 else 1
    letters_mid = n - 4 - 2 - digits_mid
    if letters_mid < 1:
        return None
    idx = 0
    out = []
    spans = [(2, "A"), (digits_mid, "D"), (letters_mid, "A"), (4, "D")]
    for count, kind in spans:
        for _ in range(count):
            ch = s[idx]
            if kind == "D" and not ch.isdigit():
                ch = _TO_DIGIT.get(ch, ch)
            elif kind == "A" and not ch.isalpha():
                ch = _TO_ALPHA.get(ch, ch)
            out.append(ch)
            idx += 1
    return "".join(out)


def normalize_plate(raw: str, country: str = "IN") -> NormalizedPlate:
    cleaned = _clean(raw)
    patterns = PATTERNS.get(country, PATTERNS["IN"])

    # already valid?
    for pat in patterns:
        if pat.match(cleaned):
            return NormalizedPlate(raw=raw, normalized=cleaned, valid_format=True, country=country)

    # attempt position-aware coercion to the standard Indian format
    coerced = _coerce_indian_standard(cleaned)
    if coerced and IND_STANDARD.match(coerced):
        return NormalizedPlate(raw=raw, normalized=coerced, valid_format=True, country=country)

    # keep the cleaned string but flag invalid format
    return NormalizedPlate(raw=raw, normalized=cleaned, valid_format=False, country=country)


def is_valid_plate(text: str, country: str = "IN") -> bool:
    cleaned = _clean(text)
    return any(p.match(cleaned) for p in PATTERNS.get(country, PATTERNS["IN"]))
