# AI Second Brain 6.0 — platform

A cloud-hosted personal knowledge service used from Claude Code through one remote MCP connector. **This repository is public**, by the owner's decision of 2026-11-10 (OD-001). Everything committed here is readable by anyone: synthetic data only, no secrets, nothing confidential.

- **Where things stand:** `backlog/DASHBOARD.md`
- **What to do next:** `python tools/backlog.py next`
- **What is blocked and why:** `docs/BLOCKERS.md`
- **Which requirement is covered, deferred or excluded:** `backlog/TRACEABILITY.md`
- **Reviews and what they found:** `docs/reviews/`
- **Rules for any session working here:** `CLAUDE.md`
- **Specification archives (unchanged):** `docs/spec/archives/`

```
pip install -e ".[dev]"
ruff check . && mypy && pytest --cov && python tools/backlog.py validate
```

Nothing here is deployed. No capability is production-ready.
