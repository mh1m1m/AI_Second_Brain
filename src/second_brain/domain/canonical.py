"""Canonical serialisation and hashing of proposals (requirements CR-31 and CR-33).

An approval is bound to these bytes. Two payloads that mean the same thing must hash the same;
any change to the payload, to what it depends on or to its class must change the hash.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Sequence
from typing import Any

CANONICAL_VERSION = "c1"


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, bool) or value is None or isinstance(value, int):
        return value
    if isinstance(value, float):
        raise TypeError("floats are not allowed in a proposal; use integers or strings")
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise TypeError("object keys must be strings")
        cleaned = {unicodedata.normalize("NFC", k): _clean(v) for k, v in value.items()}
        if len(cleaned) != len(value):
            raise ValueError("keys collide after Unicode normalisation")
        return cleaned
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    raise TypeError(f"unsupported type in proposal: {type(value).__name__}")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    body = {"v": CANONICAL_VERSION, "payload": _clean(payload)}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def proposal_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def batch_digest(proposal_hashes: Sequence[str]) -> str:
    """Digest of an ordered batch; a different order or membership gives a different digest."""
    if not proposal_hashes:
        raise ValueError("a batch needs at least one proposal")
    joined = "\n".join(proposal_hashes).encode("ascii")
    return hashlib.sha256(b"batch:" + CANONICAL_VERSION.encode("ascii") + b"\n" + joined).hexdigest()
