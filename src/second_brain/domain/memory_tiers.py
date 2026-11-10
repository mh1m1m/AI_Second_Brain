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
MAX_NOTES_RETURNED = 10


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


def expires_at(submitted_at: datetime, lifetime: timedelta = DEFAULT_NOTE_LIFETIME) -> datetime:
    return submitted_at + lifetime


def is_expired(submitted_at: datetime, now: datetime, lifetime: timedelta = DEFAULT_NOTE_LIFETIME) -> bool:
    """A note is gone at its expiry instant, not after it."""
    return now >= expires_at(submitted_at, lifetime)


def envelope(
    *,
    text: str,
    project_id: str,
    session_id: str,
    grant_id: str,
    submitted_at: datetime,
    lifetime: timedelta = DEFAULT_NOTE_LIFETIME,
) -> NoteEnvelope:
    if submitted_at.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return NoteEnvelope(
        tier=Tier.M3_UNREVIEWED_SESSION.value,
        warning=UNREVIEWED_WARNING,
        project_id=project_id,
        session_id=session_id,
        grant_id=grant_id,
        submitted_at=submitted_at.astimezone(UTC),
        expires_at=expires_at(submitted_at, lifetime).astimezone(UTC),
        text=text,
    )
