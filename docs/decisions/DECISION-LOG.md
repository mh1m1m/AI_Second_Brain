# Decision log

Provisional engineering decisions taken under the implementation authorisation of 2026-11-10. **None is an owner approval.** Owner decisions are recorded only when the owner states them.

| ID | Date | Decision | Reason | Revisit when |
|---|---|---|---|---|
| PD-001 | 2026-11-10 | Design baseline: CN1.1 as amended by addendum A1 (first-release profile) | Owner's precedence order | Verification contradicts it |
| PD-002 | 2026-11-10 | Tracking: `backlog/backlog.json` is the source of truth; board, dashboard and ticket pages are generated from it; GitHub Issues mirror it once a repository exists | GitHub Projects is unreachable from sessions (BLK-002); one source avoids drift | Projects becomes reachable |
| PD-003 | 2026-11-10 | Ticket identifiers `SB-NNN`; epics `EP-NN`; initiatives `INIT-NN` as in the owner's directive | Stable and short | — |
| PD-004 | 2026-11-10 | Review rule while there is one contributor: a ticket whose tests pass and whose self-review checklist is complete may be DONE unless it is security-relevant; security-relevant tickets stop at IN REVIEW until someone other than the author has reviewed them | The definition of done requires code review; no reviewer exists yet | A reviewer is named |
| PD-005 | 2026-11-10 | Python 3.12+, no runtime dependency until one is needed; `ruff` and `pytest` for development | Dependency minimalism carried from IR1.1 | — |
| PD-006 | 2026-11-10 | Commits are authored under the owner's name with a GitHub no-reply address | Keeps the owner's private email out of the repository | Owner prefers otherwise |
| PD-007 | 2026-11-10 | The Arabic normaliser `ar-en-1` and light stemmer `ar-light-1` are ported unchanged from the IR1.1 probe and tested against its recorded outputs | They are engine-independent and already measured | Benchmark results |
