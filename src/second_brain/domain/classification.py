"""Five-class data classification (CN1.1 document 21; requirements CR-25 and CR-29).

Pure rules only. Storage, clearance records and approval live elsewhere.

Every function accepts actual `DataClass` members and nothing else. `DataClass` is an `IntEnum`, so a plain
integer or a boolean would otherwise compare as if it were a class (99 is "not K4", True equals K1); such
values are rejected with `ClassificationError` instead. A caller must treat that error as a refusal, never
as permission. Converting stored or received values into `DataClass` is done once, by `from_label`.
"""
from __future__ import annotations

from collections.abc import Iterable
from enum import IntEnum


class DataClass(IntEnum):
    K0_PUBLIC = 0
    K1_PERSONAL = 1
    K2_CONFIDENTIAL = 2
    K3_THIRD_PARTY = 3
    K4_RESTRICTED = 4


class ClassificationError(ValueError):
    """A value that is not a classification was used as one. Always a refusal."""


UNCLASSIFIED_DEFAULT = DataClass.K2_CONFIDENTIAL
CONNECTOR_CEILING = DataClass.K1_PERSONAL  # addendum A1, AD-02: no connector grant reads above K1
_LABELS = {f"K{member.value}": member for member in DataClass}


def require(value: object, what: str = "classification") -> DataClass:
    """Return the value if it is a DataClass member; reject integers, booleans and everything else."""
    if type(value) is not DataClass:
        raise ClassificationError(f"{what} must be a DataClass member, found {type(value).__name__}")
    return value


def _flag(value: object, what: str) -> bool:
    if type(value) is not bool:
        raise ClassificationError(f"{what} must be True or False, found {type(value).__name__}")
    return value


def from_label(label: object) -> DataClass:
    """The one conversion from text: exactly 'K0' to 'K4'. Numbers and booleans are not accepted."""
    if type(label) is not str or label not in _LABELS:
        raise ClassificationError("a classification label is exactly one of K0, K1, K2, K3, K4")
    return _LABELS[label]


def resolve(declared: DataClass | None) -> DataClass:
    """Anything without a class is handled as confidential until someone classifies it."""
    return UNCLASSIFIED_DEFAULT if declared is None else require(declared, "declared class")


def highest(classes: Iterable[DataClass]) -> DataClass:
    """A record takes the highest class of its evidence. Unclassified evidence must be resolved first."""
    if isinstance(classes, str | bytes | DataClass):
        raise ClassificationError("evidence classes must be a collection of DataClass members")
    try:
        found = [require(c, "evidence class") for c in classes]
    except TypeError as exc:  # not iterable at all
        raise ClassificationError("evidence classes must be a collection of DataClass members") from exc
    if not found:
        raise ClassificationError("a record needs at least one classified piece of evidence")
    return max(found)


def storable(cls: DataClass, *, has_clearance: bool = False, admit_third_party: bool = False) -> bool:
    """K4 is never stored. K3 needs both a recorded clearance and a release that admits K3 at all."""
    cls = require(cls)
    has_clearance = _flag(has_clearance, "has_clearance")
    admit_third_party = _flag(admit_third_party, "admit_third_party")
    if cls is DataClass.K4_RESTRICTED:
        return False
    if cls is DataClass.K3_THIRD_PARTY:
        return has_clearance and admit_third_party
    return True


def readable_by_connector(cls: DataClass, ceiling: DataClass = CONNECTOR_CEILING) -> bool:
    """A connector grant never exceeds K1, whatever ceiling is asked for."""
    return require(cls) <= min(require(ceiling, "ceiling"), CONNECTOR_CEILING)


def reclassification_tier(current: DataClass, new: DataClass) -> int:
    """Raising a class is immediate (tier 0). Lowering one is a tier 2 act. No change needs nothing."""
    if require(new, "new class") < require(current, "current class"):
        return 2
    return 0
