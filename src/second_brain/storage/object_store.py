"""Object store interface for originals (requirement CR-10, decision record ADR-026).

Originals are immutable and addressed by the SHA-256 of their bytes. The interface is deliberately small:
there is no update and, in this ticket, no delete or listing; those arrive with the tickets that need them
(orphan reconciliation SB-036, retention SB-082) and will be separately authorised operations.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class ObjectStoreError(Exception):
    """Base class for object store failures."""


class ObjectNotFoundError(ObjectStoreError):
    """No object with this digest."""


class IntegrityError(ObjectStoreError):
    """Stored bytes do not match the digest they are stored under. Never returned to a caller as content."""


class InvalidDigestError(ObjectStoreError, ValueError):
    """The digest is not 64 lowercase hexadecimal characters."""


class ObjectTooLargeError(ObjectStoreError, ValueError):
    """The object exceeds the store's size limit."""


@dataclass(frozen=True, slots=True)
class ObjectRef:
    digest: str
    size: int
    created: bool  # False when identical bytes were already stored


def digest_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_digest(digest: str) -> str:
    """Validate before any use in a path or key; this is the guard against path traversal."""
    if type(digest) is not str or not _DIGEST.match(digest):
        raise InvalidDigestError("a digest is 64 lowercase hexadecimal characters")
    return digest


def check_bytes(data: bytes, max_bytes: int) -> bytes:
    if type(data) is not bytes:
        raise TypeError(f"an original is bytes, found {type(data).__name__}")
    if len(data) > max_bytes:
        raise ObjectTooLargeError(f"object of {len(data)} bytes exceeds the limit of {max_bytes}")
    return data


@runtime_checkable
class ObjectStore(Protocol):
    def put(self, data: bytes) -> ObjectRef:
        """Store bytes under their digest. Idempotent; an existing object is never overwritten."""
        ...

    def get(self, digest: str) -> bytes:
        """Return the bytes, verified against the digest, or raise ObjectNotFoundError or IntegrityError."""
        ...

    def exists(self, digest: str) -> bool:
        """Whether an object is stored under this digest. Does not verify its content."""
        ...
