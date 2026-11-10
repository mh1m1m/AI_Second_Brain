"""Adversarial vectors for the canonical proposal profile (review finding RV-01, ticket SB-012)."""
import hashlib
import json
from collections import OrderedDict
from enum import IntEnum

import pytest

from second_brain.domain import canonical
from second_brain.domain.canonical import CanonicalError, canonical_bytes, parse_proposal_json, proposal_hash

BASE = {"kind": "memory.create", "project": "p1", "class": "K1", "body": "قرار", "n": 3, "tags": ["a", "b"], "ok": True, "none": None}
GOLDEN_BYTES = '{"payload":{"body":"قرار","class":"K1","kind":"memory.create","n":3,"none":null,"ok":true,"project":"p1","tags":["a","b"]},"v":"c1"}'
GOLDEN_HASH = "481f966a84e115e70ce9a341d819d663729ed9e163d5cd9f442fb6f17395c752"
GOLDEN_BATCH = "63db634f8506654850113609eab07119f692a98e1d15f038ba4b5d48be7ea97a"

NFC, NFD = "café", "café"


# --- golden vectors and version binding -------------------------------------------------------

def test_golden_vector_pins_profile_c1():
    # If this fails, the profile changed: bump CANONICAL_VERSION and add new vectors; never edit these.
    assert canonical.CANONICAL_VERSION == "c1"
    assert canonical_bytes(BASE).decode("utf-8") == GOLDEN_BYTES
    assert proposal_hash(BASE) == GOLDEN_HASH
    assert canonical.batch_digest([proposal_hash({"n": i}) for i in range(3)]) == GOLDEN_BATCH


def test_version_is_bound_into_proposal_and_batch_hashes(monkeypatch):
    members = [proposal_hash({"n": i}) for i in range(3)]
    before = proposal_hash(BASE), canonical.batch_digest(members)
    monkeypatch.setattr(canonical, "CANONICAL_VERSION", "c2")
    assert proposal_hash(BASE) != before[0]
    assert canonical.batch_digest(members) != before[1]
    assert json.loads(canonical_bytes(BASE))["v"] == "c2"


def test_a_payload_field_cannot_impersonate_the_version_wrapper():
    assert proposal_hash({"v": "c1", "payload": BASE}) != proposal_hash(BASE)


def test_output_is_independent_of_insertion_order_and_hash_is_sha256_of_bytes():
    shuffled = dict(reversed(list(BASE.items())))
    assert canonical_bytes(shuffled) == canonical_bytes(BASE)
    assert proposal_hash(BASE) == hashlib.sha256(canonical_bytes(BASE)).hexdigest()


# --- Unicode normalisation collisions ---------------------------------------------------------

def test_equivalent_unicode_forms_hash_the_same():
    assert NFC != NFD
    assert proposal_hash({"text": NFC}) == proposal_hash({"text": NFD})
    assert proposal_hash({NFC: 1}) == proposal_hash({NFD: 1})
    assert canonical.canonical_payload({"text": NFD}) == {"text": NFC}


@pytest.mark.parametrize("payload", [
    {NFC: 1, NFD: 2},
    {NFD: 1, NFC: 2},
    {"outer": {"inner": [{NFC: "approve", NFD: "reject"}]}},
    {"Å": 1, "Å": 2},  # ANGSTROM SIGN and A WITH RING are the same after NFC
])
def test_keys_that_collide_after_normalisation_are_rejected_at_any_depth(payload):
    with pytest.raises(CanonicalError, match="normalisation"):
        proposal_hash(payload)


def test_collision_is_rejected_whichever_key_comes_first_and_no_value_is_dropped():
    for payload in ({NFC: "a", NFD: "b"}, {NFD: "b", NFC: "a"}):
        with pytest.raises(CanonicalError):
            canonical.canonical_payload(payload)


@pytest.mark.parametrize("key", ["", "role​", "‮admin", "a\u0000b", "tab\tkey", "\ud800", "", "\U000e0001"])
def test_invisible_control_and_unencodable_characters_in_keys_are_rejected(key):
    with pytest.raises(CanonicalError):
        proposal_hash({key: 1})


@pytest.mark.parametrize("text", ["\ud800", "x\udfff", "￾", "\U0001ffff", "﷐"])
def test_surrogates_and_noncharacters_in_strings_are_rejected(text):
    with pytest.raises(CanonicalError):
        proposal_hash({"text": text})


def test_distinct_strings_stay_distinct():
    # Normalisation is NFC only: compatibility forms, case and Arabic letter variants are not folded here.
    pairs = [("ﬁ", "fi"), ("A", "a"), ("أ", "ا"), ("1", "١"), ("a", "a "), ("", " ")]
    for left, right in pairs:
        assert proposal_hash({"t": left}) != proposal_hash({"t": right})


# --- duplicate JSON keys and the strict parsing boundary --------------------------------------

@pytest.mark.parametrize("text", [
    '{"decision":"reject","decision":"approve"}',
    '{"a":{"class":"K1","class":"K0"}}',
    '{"a":[{"x":1,"x":1}]}',
    '{"caf\\u00e9":1,"cafe\\u0301":2}',
    '{"a":1,"\\u0061":2}',
])
def test_duplicate_keys_in_received_json_are_rejected_at_any_depth(text):
    assert isinstance(json.loads(text), dict)  # the standard parser accepts it and keeps one value silently
    with pytest.raises(CanonicalError):
        parse_proposal_json(text)


@pytest.mark.parametrize("text", [
    '{"a":1.0}', '{"a":1e3}', '{"a":-0.0}', '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}',
    '{"a":9007199254740992}', '{"a":-9007199254740992}', '{"a":"\\ud800"}',
    "[1,2]", '"text"', "1", "null", "", "{", '{"a":1}{"a":2}', '﻿{"a":1}', "{'a':1}", '{"a":1,}',
])
def test_text_outside_the_profile_is_rejected(text):
    with pytest.raises(CanonicalError):
        parse_proposal_json(text)


def test_invalid_utf8_and_wrong_input_types_are_rejected():
    for bad in (b'{"a":"\xff"}', b"\xef\xbb\xbf{}", 7, None):
        with pytest.raises(CanonicalError):
            parse_proposal_json(bad)


def test_different_spellings_of_one_document_parse_to_the_same_hash():
    spellings = [
        '{"class":"K1","text":"caf\\u00e9","n":3}',
        ' { "n" : 3 ,\n "text" : "cafe\\u0301" , "class" : "K1" } ',
        '{"n":3,"class":"\\u004b1","text":"café"}'.encode(),
    ]
    assert len({proposal_hash(parse_proposal_json(s)) for s in spellings}) == 1


def test_parsed_canonical_bytes_round_trip_to_themselves():
    wrapped = json.loads(canonical_bytes(BASE))
    assert canonical_bytes(parse_proposal_json(json.dumps(wrapped["payload"], ensure_ascii=True))) == canonical_bytes(BASE)


# --- nested structures ------------------------------------------------------------------------

def test_nested_structures_are_canonicalised_throughout():
    a = {"changes": [{"target": {"id": "MEM-000101", "rev": 3}, "set": {"z": [1, {"b": NFD, "a": None}], "a": True}}]}
    b = {"changes": [{"set": {"a": True, "z": [1, {"a": None, "b": NFC}]}, "target": {"rev": 3, "id": "MEM-000101"}}]}
    assert proposal_hash(a) == proposal_hash(b)


@pytest.mark.parametrize(("left", "right"), [
    ({"a": [1, 2]}, {"a": [2, 1]}),
    ({"a": [[1], [2]]}, {"a": [[1, 2]]}),
    ({"a": {"b": 1}}, {"a.b": 1}),
    ({"a": []}, {"a": {}}),
    ({"a": []}, {"a": None}),
    ({"a": None}, {}),
    ({"a": [None]}, {"a": []}),
    ({"a": {"b": {"c": 1}}}, {"a": {"b": {"c": 2}}}),
])
def test_structural_differences_change_the_hash(left, right):
    assert proposal_hash(left) != proposal_hash(right)


def test_depth_limit_and_self_reference_are_rejected():
    deep: dict = {}
    cursor = deep
    for _ in range(canonical.MAX_DEPTH + 1):
        cursor["x"] = {}
        cursor = cursor["x"]
    with pytest.raises(CanonicalError, match="nested"):
        proposal_hash(deep)
    loop: dict = {}
    loop["self"] = loop
    with pytest.raises(CanonicalError):
        proposal_hash(loop)
    with pytest.raises(CanonicalError):
        parse_proposal_json("[" * 100000 + "]" * 100000)
    ok: dict = {}
    cursor = ok
    for _ in range(canonical.MAX_DEPTH):
        cursor["x"] = {}
        cursor = cursor["x"]
    assert len(proposal_hash(ok)) == 64


# --- unsupported value types ------------------------------------------------------------------

class _Level(IntEnum):
    ONE = 1


class _Text(str):
    pass


@pytest.mark.parametrize("value", [
    1.5, float("nan"), float("inf"), 0.0, b"bytes", bytearray(b"x"), {1, 2}, frozenset(), (1, 2), object(), complex(1, 2),
    _Level.ONE, _Text("x"), OrderedDict(a=1), range(3), 2**53, -(2**53), 10**400,
])
def test_unsupported_values_are_rejected_not_coerced(value):
    for payload in ({"a": value}, {"a": [value]}, {"a": {"b": value}}):
        with pytest.raises(CanonicalError):
            proposal_hash(payload)


@pytest.mark.parametrize("payload", [[1], "text", None, 1, (("a", 1),), OrderedDict(a=1)])
def test_the_payload_itself_must_be_a_plain_object(payload):
    with pytest.raises(CanonicalError):
        proposal_hash(payload)


@pytest.mark.parametrize("key", [1, None, True, 1.5, ("a",), b"a", _Text("a")])
def test_non_string_keys_are_rejected(key):
    with pytest.raises(CanonicalError):
        proposal_hash({"a": {key: 1}})


def test_values_of_different_types_never_share_a_hash():
    values = [True, 1, "1", "true", None, "null", "", 0, False, "0", [], {}, [1], ["1"], 2**53 - 1, -(2**53 - 1)]
    assert len({proposal_hash({"a": v}) for v in values}) == len(values)


# --- security-relevant fields -----------------------------------------------------------------

PROPOSAL = {
    "kind": "memory.revise", "project": "proj-alpha", "class": "K1", "tier": "M2", "scope": "project",
    "target": {"id": "MEM-000101", "rev": 3}, "evidence": [{"source": "SRC-000007", "version": 2, "locator": "p3"}],
    "body": "نص القرار", "grant": "GR-000004", "session": "SES-000012", "expires": "2026-12-01T00:00:00Z", "supersedes": None,
}


@pytest.mark.parametrize("change", [
    {"class": "K0"}, {"class": "K2"}, {"project": "proj-beta"}, {"tier": "M1"}, {"scope": "workspace"}, {"kind": "memory.delete"},
    {"target": {"id": "MEM-000102", "rev": 3}}, {"target": {"id": "MEM-000101", "rev": 4}},
    {"evidence": []}, {"evidence": [{"source": "SRC-000007", "version": 3, "locator": "p3"}]},
    {"evidence": [{"source": "SRC-000007", "version": 2, "locator": "p4"}]},
    {"body": "نص القرار."}, {"grant": "GR-000005"}, {"session": "SES-000013"}, {"expires": "2027-12-01T00:00:00Z"},
    {"supersedes": "MEM-000001"}, {"approved_by": "owner"},
])
def test_any_security_relevant_change_changes_the_hash(change):
    assert proposal_hash({**PROPOSAL, **change}) != proposal_hash(PROPOSAL)


def test_removing_any_field_changes_the_hash():
    for field in PROPOSAL:
        assert proposal_hash({k: v for k, v in PROPOSAL.items() if k != field}) != proposal_hash(PROPOSAL)


# --- batch membership and ordering ------------------------------------------------------------

def _members(n=4):
    return [proposal_hash({"n": i}) for i in range(n)]


def test_batch_digest_changes_with_order_membership_and_substitution():
    h = _members()
    digest = canonical.batch_digest(h)
    assert digest == canonical.batch_digest(tuple(h))
    assert digest != canonical.batch_digest(h[::-1])
    assert digest != canonical.batch_digest([h[1], h[0], *h[2:]])
    assert digest != canonical.batch_digest(h[:3])
    assert digest != canonical.batch_digest([*h, proposal_hash({"n": 99})])
    assert digest != canonical.batch_digest([*h[:3], proposal_hash({"n": 99})])
    assert canonical.batch_digest(h[:1]) != h[0]


@pytest.mark.parametrize("bad", [
    [], "a" * 64, None, ["a" * 63], ["A" * 64], ["g" * 64], ["a" * 64 + "\n" + "b" * 64], ["a" * 64 + "\n"], [b"a" * 64], [None],
    ["a" * 64, "a" * 64], {"a" * 64},
])
def test_malformed_or_ambiguous_batches_are_rejected(bad):
    with pytest.raises(CanonicalError):
        canonical.batch_digest(bad)


def test_two_batches_cannot_be_spliced_into_one_digest():
    h = _members()
    assert canonical.batch_digest(h) != canonical.batch_digest([canonical.batch_digest(h[:2]), canonical.batch_digest(h[2:])])
