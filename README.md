# AI Second Brain 6.0 — platform

A cloud-hosted personal knowledge service used from Claude Code through one remote MCP connector. Private repository; synthetic data only until the owner authorises otherwise.

- **Where things stand:** `backlog/DASHBOARD.md`
- **What to do next:** `python tools/backlog.py next`
- **What is blocked and why:** `docs/BLOCKERS.md`
- **Rules for any session working here:** `CLAUDE.md`
- **Specification archives (unchanged):** `docs/spec/archives/`

```
pip install -e ".[dev]"
ruff check . && pytest && python tools/backlog.py validate
```

Nothing here is deployed. No capability is production-ready.
