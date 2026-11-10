# Blockers register

| ID | Blocker | Blocks | Needs | Since |
|---|---|---|---|---|
| BLK-001 | RESOLVED 2026-11-10: the owner created `mh1m1m/AI_Second_Brain` and attached it. It is public by owner decision OD-001 | — | — | 2026-11-10 |
| BLK-002 | GitHub Projects cannot be managed from a session: the GraphQL API is unavailable there (HTTP 403, 2026-11-10) | A Projects board | Fallback in use: issues, labels, milestones and the in-repository board and dashboard | 2026-11-10 |
| BLK-003 | No cloud provider, region or budget is approved | SB-069, SB-071, SB-072 | Owner's answer to the consolidated deployment request (SB-070) | 2026-11-10 |
| BLK-004 | A reviewer is designated (OD-002: ChatGPT (GPT-6)) but no documented review has yet accepted any security-relevant ticket | DONE for SB-010, SB-011, SB-012 and every later security-relevant ticket; the security-integration gates SB-055, SB-056, SB-058, SB-060 and, through them, every release gate | The owner relays the reviewer's documented review of each ticket (request: `docs/reviews/review-request-SB-010-011-012.md`). An explicit acceptance is then recorded with `set-status SB-NNN DONE --reviewer "ChatGPT (GPT-6)" --review-ref TEXT`. Work that is not a gate continues provisionally | 2026-11-10 |
