from datetime import UTC, datetime, timedelta
from itertools import product

import pytest

from second_brain.domain import canonical, memory_tiers
from second_brain.domain.classification import (
    CONNECTOR_CEILING,
    DataClass,
    highest,
    readable_by_connector,
    reclassification_tier,
    resolve,
    storable,
)
from second_brain.domain.memory_tiers import Tier

K = DataClass


def test_unclassified_is_confidential():
    assert resolve(None) is K.K2_CONFIDENTIAL
    assert resolve(K.K0_PUBLIC) is K.K0_PUBLIC


def test_record_takes_highest_class_of_evidence():
    assert highest([K.K0_PUBLIC, K.K2_CONFIDENTIAL, K.K1_PERSONAL]) is K.K2_CONFIDENTIAL
    with pytest.raises(ValueError):
        highest([])


def test_restricted_is_never_storable_and_third_party_needs_both_conditions():
    assert not any(storable(K.K4_RESTRICTED, has_clearance=c, admit_third_party=a) for c, a in product([True, False], repeat=2))
    assert storable(K.K3_THIRD_PARTY, has_clearance=True, admit_third_party=True)
    assert not storable(K.K3_THIRD_PARTY, has_clearance=True)
    assert not storable(K.K3_THIRD_PARTY, admit_third_party=True)
    assert all(storable(c) for c in (K.K0_PUBLIC, K.K1_PERSONAL, K.K2_CONFIDENTIAL))


@pytest.mark.parametrize(("cls", "ceiling"), list(product(DataClass, DataClass)))
def test_connector_never_reads_above_personal(cls, ceiling):
    allowed = readable_by_connector(cls, ceiling)
    assert allowed == (cls <= ceiling and cls <= CONNECTOR_CEILING)
    if cls > K.K1_PERSONAL:
        assert not allowed


@pytest.mark.parametrize(("current", "new"), list(product(DataClass, DataClass)))
def test_lowering_a_class_is_tier_two(current, new):
    assert reclassification_tier(current, new) == (2 if new < current else 0)


def test_only_approved_tiers_are_searchable_and_only_sources_are_evidence():
    assert memory_tiers.SEARCHABLE_KNOWLEDGE == {Tier.M1_CANONICAL, Tier.M2_PROJECT}
    assert [t for t in Tier if memory_tiers.may_serve_as_evidence(t)] == [Tier.M4_SOURCE]
    assert all(memory_tiers.promotion_requires_approval(t) for t in Tier)


def test_envelope_always_carries_the_warning_and_expiry():
    at = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
    env = memory_tiers.envelope(text="continue with SB-022", project_id="PRJ-000001", session_id="SES-000007", grant_id="GRT-000001", submitted_at=at)
    assert env.tier == "M3" and env.warning == memory_tiers.UNREVIEWED_WARNING
    assert env.expires_at == at + timedelta(days=30)
    with pytest.raises(ValueError):
        memory_tiers.envelope(text="x", project_id="p", session_id="s", grant_id="g", submitted_at=datetime(2026, 11, 10))


def test_note_expires_at_the_boundary():
    at = datetime(2026, 11, 10, tzinfo=UTC)
    life = timedelta(days=30)
    assert not memory_tiers.is_expired(at, at + life - timedelta(seconds=1), life)
    assert memory_tiers.is_expired(at, at + life, life)


def test_hash_ignores_key_order_and_unicode_form():
    a = {"kind": "decision", "text": "café قرار", "depends": [{"id": "MEM-000101", "rev": 3}], "class": 1}
    b = {"class": 1, "depends": [{"rev": 3, "id": "MEM-000101"}], "text": "café قرار", "kind": "decision"}
    assert canonical.proposal_hash(a) == canonical.proposal_hash(b)


@pytest.mark.parametrize("change", [{"text": "other"}, {"class": 2}, {"depends": [{"id": "MEM-000101", "rev": 4}]}, {"extra": None}])
def test_any_change_changes_the_hash(change):
    base = {"kind": "decision", "text": "t", "depends": [{"id": "MEM-000101", "rev": 3}], "class": 1}
    assert canonical.proposal_hash({**base, **change}) != canonical.proposal_hash(base)


def test_list_order_matters_and_bad_values_are_rejected():
    assert canonical.proposal_hash({"a": [1, 2]}) != canonical.proposal_hash({"a": [2, 1]})
    for bad in ({"a": 1.5}, {"a": {1: "x"}}, {"a": object()}, {"café": 1, "café": 2}):
        with pytest.raises((TypeError, ValueError)):
            canonical.proposal_hash(bad)


def test_batch_digest_depends_on_order_and_membership():
    h = [canonical.proposal_hash({"n": i}) for i in range(3)]
    assert canonical.batch_digest(h) != canonical.batch_digest(h[::-1])
    assert canonical.batch_digest(h) != canonical.batch_digest(h[:2])
    with pytest.raises(ValueError):
        canonical.batch_digest([])
