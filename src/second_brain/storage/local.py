"""Filesystem adapter for the object store. For tests and local development with synthetic data only.

It is not the production store: the hosted service will use a private object storage adapter behind the
same interface once a provider is approved (SB-069, SB-070).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from second_brain.storage.object_store import (
    IntegrityError,
    ObjectNotFoundError,
    ObjectRef,
    check_bytes,
    check_digest,
    digest_of,
)

DEFAULT_MAX_BYTES = 64 * 1024 * 1024


class LocalObjectStore:
    def __init__(self, root: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self._root = Path(root)
        self._max_bytes = max_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> Path:
        check_digest(digest)
        return self._root / digest[:2] / digest[2:4] / digest

    def put(self, data: bytes) -> ObjectRef:
        check_bytes(data, self._max_bytes)
        digest = digest_of(data)
        final = self._path(digest)
        if final.exists():
            self._verify(final, digest)
            return ObjectRef(digest, len(data), created=False)
        final.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=final.parent, prefix=".incoming-")
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(name, 0o400)
            try:
                os.link(name, final)  # atomic, and fails if the object exists: nothing is ever overwritten
            except FileExistsError:
                self._verify(final, digest)
                return ObjectRef(digest, len(data), created=False)
        finally:
            os.unlink(name)
        return ObjectRef(digest, len(data), created=True)

    def get(self, digest: str) -> bytes:
        path = self._path(digest)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise ObjectNotFoundError(digest) from None
        if digest_of(data) != digest:
            raise IntegrityError(f"object {digest} does not match its digest")
        return data

    def exists(self, digest: str) -> bool:
        return self._path(digest).is_file()

    def _verify(self, path: Path, digest: str) -> None:
        if digest_of(path.read_bytes()) != digest:
            raise IntegrityError(f"object {digest} is stored with different bytes; refusing to overwrite")
