"""Canonical serialisation and hashing of proposals (requirements CR-31 and CR-33).

An approval is bound to the bytes produced here, so the contract is strict: a payload either has
exactly one canonical form or it is rejected. The profile is documented in
`docs/design/canonical-profile.md`; this module is its implementation and `CANONICAL_VERSION` its name.

Profile c1, in short:

- Values are JSON values only: object, array, string, integer, true, false, null. Exact Python types
  `dict`, `list`, `str`, `int`, `bool`, `NoneType`; subclasses, tuples, floats, bytes, sets and
  everything else are rejected rather than coerced.
- Integers lie within the interoperable range ±(2**53 - 1). Larger numbers and all decimals travel
  as strings.
- Strings are normalised to NFC. A string holding a surrogate or a Unicode noncharacter is rejected.
- Object keys are non-empty strings without control, format, surrogate, private-use or unassigned
  characters. Keys are normalised to NFC, and two keys that become equal are rejected; this is checked
  before the object is built, so no value is ever silently dropped.
- Nesting is at most `MAX_DEPTH` levels.
- Output is UTF-8 JSON without insignificant whitespace, keys sorted by Unicode code point, non-ASCII
  characters written literally, wrapped as `{"payload": ..., "v": "c1"}`.

`parse_proposal_json` is the only supported way to turn received text into a payload. It rejects
duplicate keys at every depth, floats, NaN and Infinity, a byte-order mark and invalid UTF-8, which
the standard parser would accept or silently resolve.

What is shown to the owner, hashed, stored and applied must all be `canonical_payload(...)`, never
the text as received.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

CANONICAL_VERSION = "c1"
MAX_DEPTH = 32
MAX_SAFE_INTEGER = 2**53 - 1

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_FORBIDDEN_IN_KEYS = {"Cc", "Cf", "Cs", "Co", "Cn"}


class CanonicalError(ValueError):
    """The payload has no single canonical form under the profile and must be rejected."""


def _text(value: str, where: str) -> str:
    for ch in value:
        code = ord(ch)
        if 0xD800 <= code <= 0xDFFF:
            raise CanonicalError(f"{where}: surrogate code point U+{code:04X} cannot be encoded")
        if 0xFDD0 <= code <= 0xFDEF or code & 0xFFFE == 0xFFFE:
            raise CanonicalError(f"{where}: noncharacter U+{code:04X} is not allowed")
    return unicodedata.normalize("NFC", value)


def _key(key: Any, where: str) -> str:
    if type(key) is not str:
        raise CanonicalError(f"{where}: object keys must be strings, found {type(key).__name__}")
    if not key:
        raise CanonicalError(f"{where}: empty object key")
    for ch in key:
        if unicodedata.category(ch) in _FORBIDDEN_IN_KEYS:
            raise CanonicalError(f"{where}: key holds a control or format character U+{ord(ch):04X}")
    return _text(key, where)


def _clean(value: Any, where: str, depth: int) -> Any:
    if depth > MAX_DEPTH:
        raise CanonicalError(f"{where}: nested deeper than {MAX_DEPTH} levels")
    kind = type(value)
    if kind is str:
        return _text(value, where)
    if kind is bool or value is None:
        return value
    if kind is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise CanonicalError(f"{where}: integer outside ±(2**53 - 1); send it as a string")
        return value
    if kind is dict:
        cleaned: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = _key(raw_key, where)
            if key in cleaned:
                raise CanonicalError(f"{where}: two keys become {key!r} after Unicode normalisation")
            cleaned[key] = _clean(item, f"{where}.{key}", depth + 1)
        return cleaned
    if kind is list:
        return [_clean(item, f"{where}[{i}]", depth + 1) for i, item in enumerate(value)]
    if kind is float:
        raise CanonicalError(f"{where}: floats are not allowed; use an integer or a string")
    raise CanonicalError(f"{where}: unsupported type {kind.__name__}")


def canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """The payload in canonical form, or CanonicalError. This is what is displayed, stored and applied."""
    if type(payload) is not dict:
        raise CanonicalError(f"a proposal payload is an object, found {type(payload).__name__}")
    cleaned: dict[str, Any] = _clean(payload, "payload", 0)
    return cleaned


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    body = {"v": CANONICAL_VERSION, "payload": canonical_payload(payload)}
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8")


def proposal_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CanonicalError(f"duplicate key {key!r} in received JSON")
        out[key] = value
    return out


def _no_float(text: str) -> Any:
    raise CanonicalError(f"number {text} is not an integer; send decimals as strings")


def parse_proposal_json(text: str | bytes) -> dict[str, Any]:
    """Parse received JSON strictly and return the canonical payload. The only entry point for text."""
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise CanonicalError("received bytes are not valid UTF-8") from exc
    if type(text) is not str:
        raise CanonicalError(f"JSON text expected, found {type(text).__name__}")
    if text.startswith("﻿"):
        raise CanonicalError("a byte-order mark is not allowed")
    try:
        parsed = json.loads(
            text, object_pairs_hook=_no_duplicates, parse_float=_no_float, parse_constant=_no_float
        )
    except CanonicalError:
        raise
    except (ValueError, RecursionError) as exc:
        raise CanonicalError(f"not valid JSON: {exc}") from exc
    return canonical_payload(parsed)


def batch_digest(proposal_hashes: Sequence[str]) -> str:
    """Digest of an ordered batch. Order and membership both matter; a hash may appear only once."""
    if type(proposal_hashes) not in (list, tuple):
        raise CanonicalError("a batch is a list of proposal hashes")
    if not proposal_hashes:
        raise CanonicalError("a batch needs at least one proposal")
    for item in proposal_hashes:
        if type(item) is not str or not _HASH.match(item):
            raise CanonicalError("every batch member must be a 64-character lowercase SHA-256 hex digest")
    if len(set(proposal_hashes)) != len(proposal_hashes):
        raise CanonicalError("the same proposal appears twice in the batch")
    joined = "\n".join(proposal_hashes).encode("ascii")
    return hashlib.sha256(b"batch:" + CANONICAL_VERSION.encode("ascii") + b"\n" + joined).hexdigest()
