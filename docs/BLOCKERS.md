# Blockers register

| ID | Blocker | Blocks | Needs | Since |
|---|---|---|---|---|
| BLK-001 | No GitHub repository exists for the platform, and a Claude Code session cannot create one: its GitHub access is bound to repositories already attached to it (REST call refused, 2026-11-10) | SB-005, SB-006 | Owner creates an empty private repository `ai-second-brain-platform` and grants the Claude GitHub connection access | 2026-11-10 |
| BLK-002 | GitHub Projects cannot be managed from a session: the GraphQL API is unavailable there (HTTP 403, 2026-11-10) | A Projects board | Fallback in use: issues, labels, milestones and the in-repository board and dashboard | 2026-11-10 |
| BLK-003 | No cloud provider, region or budget is approved | SB-069, SB-071, SB-072 | Owner's answer to the consolidated deployment request (SB-070) | 2026-11-10 |
