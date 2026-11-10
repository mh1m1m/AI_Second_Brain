# Review request: SB-010, SB-011, SB-012

Author: Mohammed Alsaleh · 2026-11-10 · For the designated reviewer (owner decision OD-002): ChatGPT (GPT-6), independent external code reviewer.

Review each ticket **separately** against its acceptance criteria and the security requirements it cites. The code is on `main` of `mh1m1m/AI_Second_Brain` from merge commit 6ee323e. To run the checks: `pip install -e ".[dev]" && ruff check . && pytest`.

These three modules are domain rules. None is a complete control: nothing here touches a database, a service or a connector, and their enforcement there is separate, later work (SB-027, SB-042, SB-046, SB-048, SB-058 to SB-061). Please review what exists and say what the later work must not get wrong.

## SB-010 Implement the five-class data classification model

- **What it is:** Classes K0 to K4, the default for unclassified material, the connector ceiling, the rule that a record takes the highest class of its evidence, and which reclassifications need tier 2 approval.
- **Code:** `src/second_brain/domain/classification.py`
- **Tests:** `tests/unit/test_domain.py`
- **Requirements:** CR-25, CR-29
- **Design references:** CN1.1 21; A1 03; ADR-016
- **Acceptance criteria:**
  - Unclassified input resolves to K2
  - K4 is never storable
  - `highest()` returns the maximum
  - A grant ceiling comparison is total and tested for every pair
  - Lowering a class is reported as needing tier 2

## SB-011 Implement memory tiers and the unreviewed-context envelope

- **What it is:** Tiers M1 to M4, which tiers are searchable knowledge and citable evidence, and the fixed envelope and expiry of unreviewed session notes.
- **Code:** `src/second_brain/domain/memory_tiers.py`
- **Tests:** `tests/unit/test_domain.py`
- **Requirements:** CR-42
- **Design references:** CN1.1 21; A1 03; ADR-016
- **Acceptance criteria:**
  - Only M1 and M2 are searchable knowledge
  - M3 cannot be evidence or be promoted directly
  - The envelope always carries tier, the fixed warning, session, grant, submitted and expiry times
  - Expiry is computed and enforced

## SB-012 Implement canonical serialisation and hashing of proposals

- **What it is:** Canonical profile `c1` (`docs/design/canonical-profile.md`): one byte representation per proposal or rejection, the strict JSON parsing boundary, proposal hash and batch digest.
- **Code:** `src/second_brain/domain/canonical.py`
- **Tests:** `tests/unit/test_canonical.py, tests/unit/test_domain.py`
- **Requirements:** CR-31, CR-33
- **Design references:** CN1.1 21; A1 03; ADR-016
- **Acceptance criteria:**
  - Equal payloads hash equally regardless of key order
  - Any change to payload, dependencies or class changes the hash
  - A batch digest depends on order
  - Non-JSON values are rejected
  - The canonical profile is documented and every value outside it is rejected, not coerced
  - Received JSON with duplicate keys, floats or invalid encoding is rejected at the parsing boundary
  - Keys that collide after normalisation are rejected before the object is built
  - Golden vectors pin the profile to its version

## What is asked of the reviewer

For each ticket, one of:

- **Accept**: the acceptance criteria are met and no security requirement is violated. Give the commit reviewed.
- **Accept with conditions**: list the conditions; the ticket stays IN REVIEW until they are met.
- **Reject**: list the findings; they are recorded as review issues and corrected.

Useful questions: can any input make two different proposals share a hash, or one proposal have two hashes? Can any path treat unclassified material as less than K2, or let a connector read above K1? Can an unreviewed session note become evidence or be returned without its warning? What is missing from the tests?

## How an acceptance is recorded

The owner relays the review. Only an explicit acceptance of a named ticket is recorded, as `set-status SB-NNN DONE --reviewer "ChatGPT (GPT-6)" --review-ref TEXT`, with the review stored under `docs/reviews/`. The validator refuses any other reviewer and refuses the implementer. The reviews of 2026-11-10 were preliminary and are not acceptances.
