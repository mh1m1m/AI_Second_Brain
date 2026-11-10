# AI Second Brain 6.0 — platform repository

**Mode: IMPLEMENTATION AUTHORISED** by the owner on 2026-11-10 (`docs/authorization/`). The boundaries below still apply.

## Start of every session
1. Read `backlog/DASHBOARD.md` and `docs/BLOCKERS.md`.
2. Run `python tools/github_mirror.py mh1m1m/AI_Second_Brain --check`. If it reports drift, resolve it as `backlog/README.md` describes before doing anything else.
3. Pick the highest-priority ticket whose status is READY (`python tools/backlog.py next`). A ticket marked provisional may be built and tested but not accepted.
4. Work on a branch, write tests first, run `ruff check . && pytest && python tools/backlog.py validate`.
5. Update the ticket with `python tools/backlog.py set-status SB-NNN STATUS --evidence "..."`, then `render`, then `python tools/github_mirror.py mh1m1m/AI_Second_Brain`, then commit. Tickets are changed in `backlog/backlog.json` only, never on GitHub.
6. Security-relevant tickets stop at IN REVIEW. Never record a review that did not happen, and never name the implementer as reviewer.

## This repository is public (owner decision OD-001, 2026-11-10)
Anything committed is published. Never commit secrets, real documents, personal knowledge, provider account details, or anything above class K0.

## Boundaries (do not cross without the owner's separate, explicit authorisation)
- Synthetic data only. No real documents or personal knowledge.
- No paid cloud resources, purchases or billing changes. Paid deployment needs one consolidated request (ticket SB-070).
- No employer-owned or third-party material (class K3) and nothing restricted (K4).
- No secrets in the repository, prompts or notes.
- Connector tools can read and propose only. Nothing reachable by a connector token may approve, elevate or administer.
- Every connector grant has ceiling K1. No cross-project confidential elevation.
- Unreviewed session material is never stored or returned as approved knowledge.

## Design references
`docs/spec/archives/` holds the specification archives, unchanged, with `SHA256SUMS`. Precedence: authorisation directive, then the CN1.1 addendum (A1), then CN1.1, CN1, IR1.1.
Provisional engineering choices are in `docs/decisions/DECISION-LOG.md`. They are not owner approvals.

## Status words
IMPLEMENTED, TESTED, VERIFIED, DEPLOYED, BLOCKED. Never describe something untested as working.
A ticket is DONE only under the definition in `backlog/README.md`.
