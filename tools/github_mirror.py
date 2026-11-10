#!/usr/bin/env python3
"""Mirror backlog tickets to GitHub Issues (one-way: backlog.json is the source of truth).

    python tools/github_mirror.py OWNER/REPO [--dry-run]

Uses the `gh` CLI's REST interface. Idempotent: the ticket-to-issue mapping is kept in backlog/github-issues.json.
Project tooling, not part of the service.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

import backlog

MAP = backlog.ROOT / "backlog" / "github-issues.json"
COLOURS = {"type": "1d76db", "priority": "b60205", "wave": "5319e7", "status": "0e8a16"}


def labels_for(t: dict) -> list[str]:
    return [f"type: {t['type']}", f"priority: {t['priority']}", f"wave: {t['wave']}", f"status: {t['status'].lower()}"]


def payload(t: dict, milestone: int | None, pages: dict[str, str]) -> dict:
    body = pages[f"backlog/tickets/{t['id']}.md"].split("\n", 2)[2]
    body += "\n---\nMirrored from `backlog/backlog.json`. Change the ticket there, not here."
    out = {"title": f"{t['id']} {t['title']}", "body": body, "labels": labels_for(t), "state": "closed" if t["status"] == "DONE" else "open"}
    if milestone is not None:
        out["milestone"] = milestone
    return out


def api(method: str, path: str, data: dict | None = None) -> dict | list:
    cmd = ["gh", "api", "-X", method, path]
    if data is not None:
        cmd += ["--input", "-"]
    # Arguments are a fixed list (no shell); `path` comes from this tool, not from user input.
    res = subprocess.run(cmd, input=json.dumps(data) if data is not None else None, capture_output=True, text=True, check=False)  # noqa: S603
    if res.returncode != 0:
        raise RuntimeError(f"{method} {path}: {res.stdout[:200]} {res.stderr[:200]}")
    return json.loads(res.stdout) if res.stdout.strip() else {}


def main(argv: list[str]) -> int:
    repo, dry = argv[1], "--dry-run" in argv
    data = backlog.load()
    pages = backlog.render(data)
    mapping = json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}
    wanted = sorted({lab for t in data["tickets"] for lab in labels_for(t)} | {f"status: {s.lower()}" for s in backlog.STATUSES})
    if dry:
        print(f"would ensure {len(wanted)} labels, {len({t['wave'] for t in data['tickets']})} milestones, {len(data['tickets'])} issues")
        return 0
    have = {x["name"] for x in api("GET", f"repos/{repo}/labels?per_page=100")}
    for lab in wanted:
        if lab not in have:
            api("POST", f"repos/{repo}/labels", {"name": lab, "color": COLOURS[lab.split(":")[0]]})
    stones = {m["title"]: m["number"] for m in api("GET", f"repos/{repo}/milestones?state=all&per_page=100")}
    for wave in sorted({t["wave"] for t in data["tickets"]}):
        if f"Wave {wave}" not in stones:
            stones[f"Wave {wave}"] = api("POST", f"repos/{repo}/milestones", {"title": f"Wave {wave}"})["number"]
    for t in data["tickets"]:
        body = payload(t, stones[f"Wave {t['wave']}"], pages)
        if t["id"] in mapping:
            api("PATCH", f"repos/{repo}/issues/{mapping[t['id']]}", body)
        else:
            created = api("POST", f"repos/{repo}/issues", {k: v for k, v in body.items() if k != "state"})
            mapping[t["id"]] = created["number"]
            MAP.write_text(json.dumps(mapping, indent=1) + "\n", encoding="utf-8")
            if body["state"] == "closed":
                api("PATCH", f"repos/{repo}/issues/{created['number']}", {"state": "closed"})
            time.sleep(1)
    MAP.write_text(json.dumps(mapping, indent=1) + "\n", encoding="utf-8")
    print(f"mirrored {len(mapping)} tickets to {repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
