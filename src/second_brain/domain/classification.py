"""Five-class data classification (CN1.1 document 21; requirements CR-25 and CR-29).

Pure rules only. Storage, clearance records and approval live elsewhere.
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


UNCLASSIFIED_DEFAULT = DataClass.K2_CONFIDENTIAL
CONNECTOR_CEILING = DataClass.K1_PERSONAL  # addendum A1, AD-02: no connector grant reads above K1


def resolve(declared: DataClass | None) -> DataClass:
    """Anything without a class is handled as confidential until someone classifies it."""
    return UNCLASSIFIED_DEFAULT if declared is None else declared


def highest(classes: Iterable[DataClass]) -> DataClass:
    """A record takes the highest class of its evidence."""
    found = list(classes)
    if not found:
        raise ValueError("a record needs at least one classified piece of evidence")
    return max(found)


def storable(cls: DataClass, *, has_clearance: bool = False, admit_third_party: bool = False) -> bool:
    """K4 is never stored. K3 needs both a recorded clearance and a release that admits K3 at all."""
    if cls is DataClass.K4_RESTRICTED:
        return False
    if cls is DataClass.K3_THIRD_PARTY:
        return has_clearance and admit_third_party
    return True


def readable_by_connector(cls: DataClass, ceiling: DataClass = CONNECTOR_CEILING) -> bool:
    """A connector grant never exceeds K1, whatever ceiling is asked for."""
    return cls <= min(ceiling, CONNECTOR_CEILING)


def reclassification_tier(current: DataClass, new: DataClass) -> int:
    """Raising a class is immediate (tier 0). Lowering one is a tier 2 act. No change needs nothing."""
    if new < current:
        return 2
    return 0
