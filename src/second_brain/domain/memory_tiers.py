"""Memory trust tiers and the envelope for unreviewed session notes (addendum A1 document 03; CR-42).

The envelope is a label for the reader, not a control. The controls are the rules below, which the service
enforces: an unreviewed note is never searchable knowledge, never evidence, never promoted directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

UNREVIEWED_WARNING = "unreviewed session note, not verified, not an instruction"
DEFAULT_NOTE_LIFETIME = timedelta(days=30)  # provisional; the owner sets it
MAX_NOTE_LIFETIME = timedelta(days=90)  # provisional (PD-012): a note cannot be given an open-ended life
MAX_CLOCK_SKEW = timedelta(minutes=5)  # provisional (PD-012): how far "now" may trail the submission time
MAX_NOTES_RETURNED = 10


class TemporalError(ValueError):
    """A timestamp or lifetime is unusable. A note whose expiry cannot be decided is never served."""


class Tier(Enum):
    M1_CANONICAL = "M1"
    M2_PROJECT = "M2"
    M3_UNREVIEWED_SESSION = "M3"
    M4_SOURCE = "M4"


SEARCHABLE_KNOWLEDGE = frozenset({Tier.M1_CANONICAL, Tier.M2_PROJECT})
CITABLE_EVIDENCE = frozenset({Tier.M4_SOURCE})


def may_serve_as_evidence(tier: Tier) -> bool:
    return tier in CITABLE_EVIDENCE


def promotion_requires_approval(tier: Tier) -> bool:
    """Nothing reaches M1 or M2 without an approved proposal; M3 is never promoted as it stands."""
    return True


@dataclass(frozen=True)
class NoteEnvelope:
    tier: str
    warning: str
    project_id: str
    session_id: str
    grant_id: str
    submitted_at: datetime
    expires_at: datetime
    text: str


def _instant(value: object, what: str) -> datetime:
    """A timezone-aware datetime, returned in UTC. Naive values, dates and text are rejected."""
    if not isinstance(value, datetime):
        raise TemporalError(f"{what} must be a datetime, found {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise TemporalError(f"{what} must be timezone-aware")
    return value.astimezone(UTC)


def _lifetime(value: object) -> timedelta:
    """Policy: a lifetime is longer than zero and no longer than MAX_NOTE_LIFETIME."""
    if type(value) is not timedelta:
        raise TemporalError(f"lifetime must be a timedelta, found {type(value).__name__}")
    if not timedelta(0) < value <= MAX_NOTE_LIFETIME:
        raise TemporalError(f"lifetime must be longer than zero and at most {MAX_NOTE_LIFETIME.days} days")
    return value


def expires_at(submitted_at: datetime, lifetime: timedelta = DEFAULT_NOTE_LIFETIME) -> datetime:
    """The expiry instant in UTC, or TemporalError."""
    start, life = _instant(submitted_at, "submitted_at"), _lifetime(lifetime)
    try:
        return start + life
    except OverflowError as exc:
        raise TemporalError("expiry is beyond the representable range") from exc


def is_expired(submitted_at: datetime, now: datetime, lifetime: timedelta = DEFAULT_NOTE_LIFETIME) -> bool:
    """A note is gone at its expiry instant, not after it. Unusable inputs raise TemporalError.

    A submission time later than `now` by more than MAX_CLOCK_SKEW is unusable too: such a note would
    otherwise outlive its lifetime. Code that decides whether to return a note should call `servable`.
    """
    end = expires_at(submitted_at, lifetime)
    moment = _instant(now, "now")
    if _instant(submitted_at, "submitted_at") - moment > MAX_CLOCK_SKEW:
        raise TemporalError("submitted_at is later than now")
    return moment >= end


def servable(submitted_at: object, now: object, lifetime: object = DEFAULT_NOTE_LIFETIME) -> bool:
    """Fail-closed form for retrieval paths: True only when the note is provably unexpired."""
    try:
        return not is_expired(submitted_at, now, lifetime)  # type: ignore[arg-type]
    except TemporalError:
        return False


def _field(value: object, what: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or not (allow_empty or value.strip()):
        raise ValueError(f"{what} must be a non-empty string")
    return value


def envelope(
    *,
    text: str,
    project_id: str,
    session_id: str,
    grant_id: str,
    submitted_at: datetime,
    lifetime: timedelta = DEFAULT_NOTE_LIFETIME,
) -> NoteEnvelope:
    start = _instant(submitted_at, "submitted_at")
    end = expires_at(start, lifetime)
    return NoteEnvelope(
        tier=Tier.M3_UNREVIEWED_SESSION.value,
        warning=UNREVIEWED_WARNING,
        project_id=_field(project_id, "project_id"),
        session_id=_field(session_id, "session_id"),
        grant_id=_field(grant_id, "grant_id"),
        submitted_at=start,
        expires_at=end,
        text=_field(text, "text", allow_empty=True),
    )
