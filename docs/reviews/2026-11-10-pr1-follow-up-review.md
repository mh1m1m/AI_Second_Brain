# Follow-up independent review of pull requests #1 and #87: outcome

Author: Mohammed Alsaleh · Recorded 2026-11-10 · Source: the external reviewer's follow-up, supplied by the owner in the session. Summarised here; the reviewer's text is not reproduced.

The reviewer inspected commit 433bdf3 (pull request #1) and the stacked pull request #87, and recommended approving the corrected foundation for merging, subject to one additional safeguard. Merging remains the owner's decision.

## Assessment of the five findings

| ID | Reviewer's assessment | Note |
|---|---|---|
| RV-01 canonical hashing | Corrected | Strict parsing, duplicate-key rejection, collision detection, bounded integers, nesting limit |
| RV-02 requirements traceability | Corrected | The discrepancy is explained; all 148 requirements have a disposition |
| RV-03 security dependency gates | Corrected | Security-integration and release gates need completed prerequisites |
| RV-04 missing initiatives | Corrected | The three initiatives have epics and tickets |
| RV-05 issue synchronisation | Corrected, with a limitation | The fingerprint and marker detect accidental divergence, not malicious modification. Acceptable for the development workflow **provided it is never treated as a security boundary** |

## New item

| ID | Item | Where it lands | State |
|---|---|---|---|
| RV-06 | Before the approval workflow is accepted, an end-to-end test must prove that the exact canonical payload displayed to the owner is the payload hashed, approved, stored and applied | Acceptance criteria added to SB-058 (display), SB-060 (apply) and SB-061 (the end-to-end test); obligation 5 in `docs/design/canonical-profile.md` | Open. The approval workflow does not exist yet, so the test cannot be written yet. All three tickets are behind closed gates |

## On pull request #87

The object store abstraction and the type-checking and coverage steps were judged reasonable. The reviewer's caution is recorded as a standing rule for reports: full coverage of the current modules says nothing about the parts of the system that do not exist yet.

## Governance: what this review is not

The reviewer stated that the review is technical feedback and that SB-010, SB-011 and SB-012 should not be marked DONE because of it. They stay IN REVIEW. Decision PD-004 needs two things that only the owner can supply:

1. an explicitly designated independent reviewer;
2. a recorded acceptance decision for each security-relevant ticket (`set-status SB-NNN DONE --reviewer NAME --review-ref TEXT`).

Until then the security-integration gates SB-055, SB-056, SB-058 and SB-060 stay closed (blocker BLK-004). Work that is not a gate continues.

## Reviewer's recommended order

1. Record this outcome and designate the reviewer. *Outcome recorded here; the designation is the owner's.*
2. Merge pull request #1 after confirming CI is green. *CI on 433bdf3 is green for both events; merging is the owner's action.*
3. Verify pull request #87 against the merged branch, then merge it.
4. Continue with SB-020, SB-050 and SB-051.
5. Keep the security-integration gates closed until their reviews are recorded. *Enforced by the validator.*

The reviewer names the next meaningful milestone as a working PostgreSQL-backed service with its security boundaries enforced, not more unit tests.
