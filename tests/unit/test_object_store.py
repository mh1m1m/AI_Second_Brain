"""Object store interface and local adapter (ticket SB-032, requirement CR-10). Synthetic bytes only."""
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from second_brain.storage.local import LocalObjectStore
from second_brain.storage.object_store import (
    IntegrityError,
    InvalidDigestError,
    ObjectNotFoundError,
    ObjectStore,
    ObjectTooLargeError,
    check_digest,
    digest_of,
)

DATA = "نص تجريبي synthetic sample\n".encode()


@pytest.fixture
def store(tmp_path):
    return LocalObjectStore(tmp_path / "objects")


def _files(tmp_path):
    return sorted(p for p in (tmp_path / "objects").rglob("*") if p.is_file())


def test_adapter_satisfies_the_interface(store):
    assert isinstance(store, ObjectStore)


def test_put_then_get_round_trips_and_is_addressed_by_sha256(store):
    ref = store.put(DATA)
    assert ref.digest == digest_of(DATA) and ref.size == len(DATA) and ref.created is True
    assert store.exists(ref.digest) and store.get(ref.digest) == DATA


def test_put_is_idempotent_by_content_hash(store, tmp_path):
    first, second = store.put(DATA), store.put(DATA)
    assert first.digest == second.digest and first.created is True and second.created is False
    assert len(_files(tmp_path)) == 1


def test_different_bytes_get_different_objects_and_empty_bytes_are_allowed(store, tmp_path):
    digests = {store.put(x).digest for x in (DATA, DATA + b" ", b"")}
    assert len(digests) == 3 and len(_files(tmp_path)) == 3
    assert store.get(digest_of(b"")) == b""


def test_an_existing_object_is_never_overwritten(store, tmp_path):
    ref = store.put(DATA)
    path = _files(tmp_path)[0]
    before = path.stat()
    store.put(DATA)
    after = path.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
    assert stat.S_IMODE(after.st_mode) == 0o400
    os.chmod(path, 0o600)
    path.write_bytes(b"tampered")
    with pytest.raises(IntegrityError, match="refusing to overwrite"):
        store.put(DATA)
    assert path.read_bytes() == b"tampered"  # the evidence of tampering is left in place, not repaired silently
    assert ref.digest == digest_of(DATA)


def test_get_verifies_the_checksum(store, tmp_path):
    ref = store.put(DATA)
    path = _files(tmp_path)[0]
    os.chmod(path, 0o600)
    path.write_bytes(DATA[:-1])
    with pytest.raises(IntegrityError):
        store.get(ref.digest)


def test_missing_objects_and_bad_digests_are_distinct_errors(store):
    with pytest.raises(ObjectNotFoundError):
        store.get(digest_of(b"absent"))
    assert store.exists(digest_of(b"absent")) is False
    for bad in ("", "abc", "A" * 64, "g" * 64, "../" * 21 + "x", "a" * 63 + "/", "a" * 65, None, 7, digest_of(b"x").encode()):
        with pytest.raises(InvalidDigestError):
            store.get(bad)
        with pytest.raises(InvalidDigestError):
            store.exists(bad)
    assert check_digest("a" * 64) == "a" * 64


def test_only_bytes_within_the_size_limit_are_accepted(tmp_path):
    small = LocalObjectStore(tmp_path / "objects", max_bytes=8)
    assert small.put(b"12345678").size == 8
    with pytest.raises(ObjectTooLargeError):
        small.put(b"123456789")
    for bad in ("text", bytearray(b"x"), memoryview(b"x"), None, 1):
        with pytest.raises(TypeError):
            small.put(bad)
    assert len(_files(tmp_path)) == 1


def test_concurrent_puts_of_the_same_bytes_store_one_object_and_leave_no_temporary_file(store, tmp_path):
    with ThreadPoolExecutor(max_workers=16) as pool:
        refs = list(pool.map(lambda _: store.put(DATA), range(64)))
    assert {r.digest for r in refs} == {digest_of(DATA)}
    assert sum(r.created for r in refs) == 1
    files = _files(tmp_path)
    assert len(files) == 1 and not any(p.name.startswith(".incoming-") for p in files)
    assert store.get(refs[0].digest) == DATA


def test_objects_stay_inside_the_root(store, tmp_path):
    store.put(DATA)
    root = (tmp_path / "objects").resolve()
    assert all(root in p.resolve().parents for p in _files(tmp_path))


def test_a_put_that_loses_the_race_keeps_the_existing_object(store, tmp_path, monkeypatch):
    store.put(DATA)
    inode = _files(tmp_path)[0].stat().st_ino
    monkeypatch.setattr(Path, "exists", lambda self: False)  # another writer finished between the check and the link
    ref = store.put(DATA)
    monkeypatch.undo()
    files = _files(tmp_path)
    assert ref.created is False and len(files) == 1 and files[0].stat().st_ino == inode
