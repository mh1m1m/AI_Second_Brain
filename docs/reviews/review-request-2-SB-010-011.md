# Second review request: SB-010 and SB-011 (conditions RV-07 and RV-08)

Author: Mohammed Alsaleh · 2026-11-10 · For the designated reviewer (owner decision OD-002): ChatGPT (GPT-6).

A focused review of the corrections to the two conditions of the review of 2026-11-10. Nothing else in these tickets changed. To run: `pip install -e ".[dev]" && ruff check . && mypy && pytest --cov`.

## SB-010, condition RV-07: reject values that are not `DataClass` members

- **Code:** `src/second_brain/domain/classification.py` (`require`, `_flag`, `from_label`, and their use in `resolve`, `highest`, `storable`, `readable_by_connector`, `reclassification_tier`)
- **Tests:** `tests/unit/test_domain_adversarial.py`, section RV-07; unchanged behaviour in `tests/unit/test_domain.py`
- **Required actions and where each is met:**
  1. Strict type validation at classification boundaries: `require` uses an exact type check, in every public function.
  2. Reject unsupported integers, booleans and other types: 21 non-member values are tried against every function and argument position, including `storable(99)`.
  3. Adversarial tests: as above, plus flags that are truthy but not booleans, and labels that are almost right.
  4. Preserve the K1 ceiling and the K4 prohibition: re-tested over every class and ceiling pair.

## SB-011, condition RV-08: validate timestamps and lifetimes consistently

- **Code:** `src/second_brain/domain/memory_tiers.py` (`_instant`, `_lifetime`, `expires_at`, `is_expired`, `servable`, `envelope`)
- **Tests:** `tests/unit/test_domain_adversarial.py`, section RV-08
- **Required actions and where each is met:**
  1. Timezone-aware timestamps everywhere: `_instant` is called by every function that takes a time.
  2. Validate lifetimes: `_lifetime`; policy is longer than zero and at most 90 days.
  3. Reject invalid temporal inputs safely: `TemporalError` from the strict functions; `servable` returns False and never raises.
  4. Timezone and boundary regression tests: five offsets around the exact expiry instant, equal instants in different offsets, a wall clock that reads earlier but is later.
  5. Database and service enforcement remains required: stated in the module, on the ticket, and carried by SB-027, SB-046 and SB-079.

## Points on which a view is specifically asked

- Is raising on invalid input, with `servable` as the fail-closed predicate, the right split, or should `is_expired` itself return True on invalid input?
- Are the provisional limits (90 days, five minutes of clock tolerance) acceptable as defaults pending the owner's decision?
- Is refusing every integer, with `from_label` as the only conversion, too strict for the database layer to use correctly?

## Response

For each ticket: **Accept**, **Accept with conditions**, or **Reject**, with the commit inspected. Only an explicit acceptance of a named ticket is recorded as DONE.
