"""Adversarial inputs at the domain boundary: conditions of the security review of 2026-11-10 (RV-07 on SB-010, RV-08 on SB-011)."""
from datetime import UTC, date, datetime, timedelta, timezone
from enum import IntEnum
from itertools import product

import pytest

from second_brain.domain import classification as c
from second_brain.domain import memory_tiers as m
from second_brain.domain.classification import ClassificationError, DataClass

K = DataClass


class Lookalike(IntEnum):
    K1_PERSONAL = 1


NOT_A_CLASS = [99, -1, 0, 1, 2, 4, 5, True, False, 1.0, "K1", "1", "K1_PERSONAL", b"K1", None, [], (K.K1_PERSONAL,), {K.K1_PERSONAL}, Lookalike.K1_PERSONAL, object(), DataClass]


# --- RV-07: classification accepts DataClass members and nothing else -------------------------

@pytest.mark.parametrize("bad", NOT_A_CLASS)
def test_every_classification_function_rejects_values_that_are_not_members(bad):
    with pytest.raises(ClassificationError):
        c.require(bad)
    with pytest.raises(ClassificationError):
        c.storable(bad)
    with pytest.raises(ClassificationError):
        c.storable(bad, has_clearance=True, admit_third_party=True)
    with pytest.raises(ClassificationError):
        c.readable_by_connector(bad)
    with pytest.raises(ClassificationError):
        c.readable_by_connector(K.K0_PUBLIC, bad)
    with pytest.raises(ClassificationError):
        c.reclassification_tier(bad, K.K0_PUBLIC)
    with pytest.raises(ClassificationError):
        c.reclassification_tier(K.K4_RESTRICTED, bad)
    with pytest.raises(ClassificationError):
        c.highest([K.K0_PUBLIC, bad])
    if bad is not None:  # None alone means "unclassified" to resolve, and nothing else does
        with pytest.raises(ClassificationError):
            c.resolve(bad)


def test_the_reviewers_example_is_refused():
    with pytest.raises(ClassificationError):
        c.storable(99)


def test_an_integer_cannot_slip_under_the_connector_ceiling_or_past_the_k4_rule():
    for bad in (0, 1, True, False, -5):
        with pytest.raises(ClassificationError):
            c.readable_by_connector(bad)  # 0 and 1 compare as "at most K1" if not rejected
    for bad in (4, 99, 4.0, "K4"):
        with pytest.raises(ClassificationError):
            c.storable(bad)  # none of these "is K4", so each would have been storable


@pytest.mark.parametrize("flag", [1, 0, "yes", "", "false", None, [], [0], 1.0, object()])
def test_clearance_flags_must_be_real_booleans(flag):
    with pytest.raises(ClassificationError):
        c.storable(K.K3_THIRD_PARTY, has_clearance=flag, admit_third_party=True)
    with pytest.raises(ClassificationError):
        c.storable(K.K3_THIRD_PARTY, has_clearance=True, admit_third_party=flag)
    with pytest.raises(ClassificationError):
        c.storable(K.K0_PUBLIC, has_clearance=flag)


@pytest.mark.parametrize("bad", ["K1", b"\x01", K.K1_PERSONAL, 5, None, [None], [K.K0_PUBLIC, None], [[K.K0_PUBLIC]], []])
def test_highest_needs_a_non_empty_collection_of_members(bad):
    with pytest.raises(ClassificationError):
        c.highest(bad)


def test_highest_accepts_any_iterable_of_members():
    assert c.highest(iter([K.K0_PUBLIC, K.K3_THIRD_PARTY])) is K.K3_THIRD_PARTY
    assert c.highest({K.K1_PERSONAL}) is K.K1_PERSONAL
    assert c.highest(x for x in DataClass) is K.K4_RESTRICTED


def test_labels_are_the_only_conversion_and_are_exact():
    assert [c.from_label(f"K{i}") for i in range(5)] == list(DataClass)
    for bad in ("k1", "K5", "K-1", " K1", "K1 ", "K01", "1", "", "K1_PERSONAL", 1, True, None, b"K1", K.K1_PERSONAL, "K١"):
        with pytest.raises(ClassificationError):
            c.from_label(bad)


def test_valid_behaviour_is_unchanged_k4_never_stored_and_connector_ceiling_is_k1():
    assert c.resolve(None) is K.K2_CONFIDENTIAL and all(c.resolve(k) is k for k in DataClass)
    assert not any(c.storable(K.K4_RESTRICTED, has_clearance=a, admit_third_party=b) for a, b in product([True, False], repeat=2))
    assert [c.storable(k) for k in DataClass] == [True, True, True, False, False]
    assert c.storable(K.K3_THIRD_PARTY, has_clearance=True, admit_third_party=True)
    for cls, ceiling in product(DataClass, DataClass):
        assert c.readable_by_connector(cls, ceiling) == (cls <= ceiling and cls <= K.K1_PERSONAL)
    assert c.CONNECTOR_CEILING is K.K1_PERSONAL and c.UNCLASSIFIED_DEFAULT is K.K2_CONFIDENTIAL
    assert issubclass(ClassificationError, ValueError)


# --- RV-08: timestamps and lifetimes are validated in every function --------------------------

AT = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
RIYADH = timezone(timedelta(hours=3))
NOT_AN_INSTANT = [datetime(2026, 11, 10, 9, 0), date(2026, 11, 10), "2026-11-10T09:00:00+00:00", 1794301200, 1794301200.0, None, AT.time(), AT.timetz()]
NOT_A_LIFETIME = [timedelta(0), timedelta(seconds=-1), timedelta(days=-30), timedelta(days=90, microseconds=1), timedelta(days=3650), timedelta.max, timedelta.min, 30, 30.0, "30 days", None, True]


@pytest.mark.parametrize("bad", NOT_AN_INSTANT)
def test_naive_and_non_datetime_timestamps_are_rejected_everywhere(bad):
    with pytest.raises(m.TemporalError):
        m.expires_at(bad)
    with pytest.raises(m.TemporalError):
        m.is_expired(bad, AT)
    with pytest.raises(m.TemporalError):
        m.is_expired(AT, bad)
    with pytest.raises(m.TemporalError):
        m.envelope(text="x", project_id="p", session_id="s", grant_id="g", submitted_at=bad)
    assert m.servable(bad, AT) is False and m.servable(AT, bad) is False


@pytest.mark.parametrize("bad", NOT_A_LIFETIME)
def test_lifetimes_outside_the_policy_are_rejected_everywhere(bad):
    with pytest.raises(m.TemporalError):
        m.expires_at(AT, bad)
    with pytest.raises(m.TemporalError):
        m.is_expired(AT, AT, bad)
    with pytest.raises(m.TemporalError):
        m.envelope(text="x", project_id="p", session_id="s", grant_id="g", submitted_at=AT, lifetime=bad)
    assert m.servable(AT, AT, bad) is False


def test_lifetime_policy_bounds_are_explicit():
    assert m.expires_at(AT, timedelta(microseconds=1)) == AT + timedelta(microseconds=1)
    assert m.expires_at(AT, m.MAX_NOTE_LIFETIME) == AT + timedelta(days=90)
    assert timedelta(0) < m.DEFAULT_NOTE_LIFETIME <= m.MAX_NOTE_LIFETIME


def test_the_same_instant_in_different_offsets_gives_the_same_expiry_in_utc():
    local = AT.astimezone(RIYADH)
    west = AT.astimezone(timezone(timedelta(hours=-11, minutes=-30)))
    assert local.hour == 12 and m.expires_at(local) == m.expires_at(west) == m.expires_at(AT) == AT + timedelta(days=30)
    assert m.expires_at(local).utcoffset() == timedelta(0)
    env = m.envelope(text="x", project_id="p", session_id="s", grant_id="g", submitted_at=local)
    assert env.submitted_at == AT and env.submitted_at.tzinfo is UTC and env.expires_at.tzinfo is UTC


@pytest.mark.parametrize("zone", [UTC, RIYADH, timezone(timedelta(hours=-8)), timezone(timedelta(hours=14)), timezone(timedelta(hours=5, minutes=45))])
def test_expiry_boundary_is_exact_whatever_offset_now_is_given_in(zone):
    life = timedelta(days=30)
    end = AT + life
    assert m.is_expired(AT, (end - timedelta(microseconds=1)).astimezone(zone), life) is False
    assert m.is_expired(AT, end.astimezone(zone), life) is True
    assert m.is_expired(AT, (end + timedelta(microseconds=1)).astimezone(zone), life) is True
    assert m.servable(AT, (end - timedelta(microseconds=1)).astimezone(zone), life) is True
    assert m.servable(AT, end.astimezone(zone), life) is False


def test_a_wall_clock_that_looks_earlier_but_is_later_still_expires_the_note():
    end = AT + timedelta(days=30)                       # 09:00 UTC
    later = datetime(end.year, end.month, end.day, 8, 30, tzinfo=timezone(timedelta(hours=-1)))  # reads 08:30, is 09:30 UTC
    assert m.is_expired(AT, later) is True


def test_a_submission_time_in_the_future_cannot_extend_a_notes_life():
    assert m.is_expired(AT + m.MAX_CLOCK_SKEW, AT) is False  # within tolerated skew
    with pytest.raises(m.TemporalError):
        m.is_expired(AT + m.MAX_CLOCK_SKEW + timedelta(microseconds=1), AT)
    assert m.servable(AT + timedelta(days=365), AT) is False


def test_dates_at_the_edge_of_the_calendar_fail_safely():
    edge = datetime.max.replace(tzinfo=UTC)
    with pytest.raises(m.TemporalError):
        m.expires_at(edge)
    assert m.servable(edge, edge) is False


def test_servable_never_raises_and_is_true_only_for_a_provably_live_note():
    assert m.servable(AT, AT) is True and m.servable(AT, AT + timedelta(days=29)) is True
    for args in product([*NOT_AN_INSTANT, AT], [*NOT_AN_INSTANT, AT], [*NOT_A_LIFETIME, m.DEFAULT_NOTE_LIFETIME]):
        expected = args == (AT, AT, m.DEFAULT_NOTE_LIFETIME)
        assert m.servable(*args) is expected


@pytest.mark.parametrize("field", ["project_id", "session_id", "grant_id", "text"])
@pytest.mark.parametrize("bad", [None, 7, b"x", ["x"]])
def test_envelope_fields_must_be_strings(field, bad):
    good = {"text": "x", "project_id": "p", "session_id": "s", "grant_id": "g", "submitted_at": AT}
    with pytest.raises(ValueError):
        m.envelope(**{**good, field: bad})


def test_envelope_identifiers_cannot_be_blank_and_the_envelope_is_unchanged_otherwise():
    for field in ("project_id", "session_id", "grant_id"):
        with pytest.raises(ValueError):
            m.envelope(**{"text": "x", "project_id": "p", "session_id": "s", "grant_id": "g", "submitted_at": AT, field: "  "})
    env = m.envelope(text="", project_id="p", session_id="s", grant_id="g", submitted_at=AT)
    assert (env.tier, env.warning, env.expires_at) == ("M3", m.UNREVIEWED_WARNING, AT + timedelta(days=30))
    assert issubclass(m.TemporalError, ValueError)
