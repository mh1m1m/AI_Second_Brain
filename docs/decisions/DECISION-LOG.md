# Decision log

Provisional engineering decisions taken under the implementation authorisation of 2026-11-10. **None is an owner approval.** Owner decisions are recorded only when the owner states them.

## Owner decisions

| ID | Date | Decision | Recorded from |
|---|---|---|---|
| OD-001 | 2026-11-10 | The platform repository is `mh1m1m/AI_Second_Brain` and stays **public**. The owner was told that the specification and the directive call for a private repository and that the threat model and residual-risk register would be published, and chose to push as public | The owner's answer in the session |
| OD-002 | 2026-11-10 | The designated independent reviewer for security-relevant tickets is **ChatGPT (GPT-6), acting as independent external code reviewer**. It is to review SB-010, SB-011 and SB-012 separately against their acceptance criteria and security requirements. No ticket is marked DONE until a documented independent review explicitly accepts it. The reviews of 2026-11-10 were preliminary and are not that acceptance | The owner's answer in the session |
| OD-003 | 2026-11-10 | Merge pull request #1, then pull request #87 after its CI is confirmed | The owner's answer in the session |

## Provisional engineering decisions

| ID | Date | Decision | Reason | Revisit when |
|---|---|---|---|---|
| PD-001 | 2026-11-10 | Design baseline: CN1.1 as amended by addendum A1 (first-release profile) | Owner's precedence order | Verification contradicts it |
| PD-002 | 2026-11-10 | Tracking: `backlog/backlog.json` is the source of truth; board, dashboard and ticket pages are generated from it; GitHub Issues mirror it once a repository exists | GitHub Projects is unreachable from sessions (BLK-002); one source avoids drift | Projects becomes reachable |
| PD-003 | 2026-11-10 | Ticket identifiers `SB-NNN`; epics `EP-NN`; initiatives `INIT-NN` as in the owner's directive | Stable and short | — |
| PD-004 | 2026-11-10, amended after review finding RV-03 | Review rule while there is one contributor: a ticket whose tests pass and whose self-review checklist is complete may be DONE unless it is security-relevant (`security_relevant` in the backlog); a security-relevant ticket stops at IN REVIEW and becomes DONE only with a recorded review (reviewer, date, reference) by someone other than the implementer. The validator enforces this | The definition of done requires code review; no reviewer exists yet | A reviewer is named |
| PD-005 | 2026-11-10 | Python 3.12+, no runtime dependency until one is needed; `ruff` and `pytest` for development | Dependency minimalism carried from IR1.1 | — |
| PD-006 | 2026-11-10 | Commits are authored under the owner's name with a GitHub no-reply address | Keeps the owner's private email out of the repository | Owner prefers otherwise |
| PD-007 | 2026-11-10 | The Arabic normaliser `ar-en-1` and light stemmer `ar-light-1` are ported unchanged from the IR1.1 probe and tested against its recorded outputs | They are engine-independent and already measured | Benchmark results |
| PD-008 | 2026-11-10 | Readiness and acceptance are separate (review finding RV-03). Ordinary tickets may start provisionally on dependencies that are DONE or IN REVIEW. Gate tickets, marked `security-integration` (SB-055, SB-056, SB-058, SB-060) or `release` (SB-070, SB-071, SB-074, SB-078), become READY only when every dependency is DONE. No ticket is DONE before its dependencies | Later work must not be accepted, integrated or released on security assumptions nobody has reviewed | The owner sets a different gate list |
| PD-009 | 2026-11-10 | `backlog/backlog.json` is the only place a ticket is changed (review finding RV-05). The mirror records what it pushed, reports issues edited on GitHub, refuses to overwrite them without `--accept-backlog`, and an unpushed backlog change fails the tests | One source of truth with detected, not silent, divergence; full two-way synchronisation is not justified for one contributor | A second contributor works from GitHub Issues |
| PD-010 | 2026-11-10 | Canonical proposal profile `c1` as in `docs/design/canonical-profile.md` (review finding RV-01): strict JSON value set, NFC, rejection instead of coercion, integers within ±(2^53 − 1), code-point key order | An approval must bind to one representation only | Independent review of SB-012, or a need to interoperate with RFC 8785 |
| PD-011 | 2026-11-10 | Requirement dispositions (review finding RV-02): 11 IR1.1 requirements marked SUPERSEDED by the CN1.1 transition are excluded with their replacements; the 3 legacy-import requirements the specification defers stay deferred; the isolated extraction worker (CR-23) is scheduled as SB-085 rather than deferred; elevation under CR-39 is not built | Every requirement needs a ticket, a deferral or an exclusion | The owner disagrees with any single disposition in `backlog/TRACEABILITY.md` |
| PD-012 | 2026-11-10 | Unreviewed session notes: a lifetime must be longer than zero and at most 90 days (default 30); a submission time may be at most 5 minutes later than the clock, otherwise the note is refused; any expiry that cannot be decided is treated as expired (review condition RV-08) | The reviewer asked for an explicit policy on zero and negative lifetimes; an upper bound and a future-time rule close the same hole from the other side | The owner sets the lifetime limits |
