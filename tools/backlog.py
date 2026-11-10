#!/usr/bin/env python3
"""Backlog tool. `backlog/backlog.json` is the source of truth; everything else under `backlog/` is generated from it.

    python tools/backlog.py validate | render [--check] | next | set-status SB-NNN STATUS [--evidence TEXT] [--reason TEXT]
    python tools/backlog.py record-tests PASSED FAILED

Standard library only. This is project tooling, not part of the service.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backlog" / "backlog.json"
STATUSES = ["BACKLOG", "READY", "IN PROGRESS", "IN REVIEW", "TESTING", "BLOCKED", "DONE", "REOPENED"]
SATISFIED = {"DONE", "IN REVIEW"}  # a dependency in review is implemented and tested; see backlog/README.md
PRIORITIES = ["P0", "P1", "P2", "P3"]
TYPES = ["epic", "feature", "task", "bug", "security", "research", "debt"]


def load(path: Path = SRC) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(data: dict, path: Path = SRC) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def find_cycle(tickets: dict[str, dict]) -> list[str]:
    state: dict[str, int] = {}

    def visit(node: str) -> list[str]:
        if state.get(node) == 1:
            return [node]
        if state.get(node) == 2:
            return []
        state[node] = 1
        for dep in tickets[node]["depends_on"]:
            if dep in tickets:
                found = visit(dep)
                if found:
                    return [node, *found]
        state[node] = 2
        return []

    for name in tickets:
        found = visit(name)
        if found:
            return found
    return []


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    ids = [t["id"] for t in data["tickets"]]
    errors += [f"duplicate id {i}" for i, n in Counter(ids).items() if n > 1]
    tickets = {t["id"]: t for t in data["tickets"]}
    epics = {e["id"] for e in data["epics"]}
    for t in data["tickets"]:
        tid = t["id"]
        if t["epic"] not in epics:
            errors.append(f"{tid}: unknown epic {t['epic']}")
        if t["status"] not in STATUSES:
            errors.append(f"{tid}: unknown status {t['status']}")
        if t["priority"] not in PRIORITIES or t["type"] not in TYPES:
            errors.append(f"{tid}: bad priority or type")
        errors += [f"{tid}: unknown dependency {d}" for d in t["depends_on"] if d not in tickets]
        if not t["acceptance"]:
            errors.append(f"{tid}: no acceptance criteria")
        if t["status"] in ("DONE", "IN REVIEW") and not t["evidence"]:
            errors.append(f"{tid}: {t['status']} without evidence")
        if t["status"] == "BLOCKED" and not t.get("blocked_reason"):
            errors.append(f"{tid}: BLOCKED without a reason")
        if t["status"] in ("READY", "IN PROGRESS", "IN REVIEW", "TESTING", "DONE"):
            unmet = [d for d in t["depends_on"] if d in tickets and tickets[d]["status"] not in SATISFIED]
            if unmet:
                errors.append(f"{tid}: {t['status']} but dependencies not satisfied: {', '.join(unmet)}")
    for e in data["epics"]:
        if e["initiative"] not in data["initiatives"]:
            errors.append(f"{e['id']}: unknown initiative {e['initiative']}")
    cycle = find_cycle(tickets)
    if cycle:
        errors.append("dependency cycle: " + " -> ".join(cycle))
    return errors


def refresh(data: dict) -> None:
    """BACKLOG becomes READY when every dependency is satisfied, and the reverse."""
    tickets = {t["id"]: t for t in data["tickets"]}
    for t in data["tickets"]:
        met = all(tickets[d]["status"] in SATISFIED for d in t["depends_on"])
        if t["status"] == "BACKLOG" and met:
            t["status"] = "READY"
        elif t["status"] == "READY" and not met:
            t["status"] = "BACKLOG"


def critical_path(data: dict) -> tuple[int, list[str]]:
    """Longest chain of unfinished work, weighted by points."""
    tickets = {t["id"]: t for t in data["tickets"]}
    memo: dict[str, tuple[int, list[str]]] = {}

    def best(tid: str) -> tuple[int, list[str]]:
        if tid in memo:
            return memo[tid]
        t = tickets[tid]
        own = 0 if t["status"] == "DONE" else t["points"]
        top = max((best(d) for d in t["depends_on"]), default=(0, []))
        memo[tid] = (top[0] + own, [*top[1], tid] if own else top[1])
        return memo[tid]

    return max((best(t) for t in tickets), default=(0, []))


def table(head: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return [*out, ""]


def pct(a: int, b: int) -> str:
    return f"{round(100 * a / b)}%" if b else "—"


def render(data: dict) -> dict[str, str]:
    tickets = data["tickets"]
    by_id = {t["id"]: t for t in tickets}
    epics = {e["id"]: e for e in data["epics"]}
    files: dict[str, str] = {}
    note = "<!-- Generated by tools/backlog.py from backlog/backlog.json. Do not edit by hand. -->"
    done = [t for t in tickets if t["status"] == "DONE"]
    pts = sum(t["points"] for t in tickets)
    status_count = Counter(t["status"] for t in tickets)
    open_waves = sorted({t["wave"] for t in tickets if t["status"] != "DONE"})
    length, path = critical_path(data)
    tests = data.get("last_test_run")
    d = [note, "# Dashboard", "", "Computed from ticket states. A ticket counts as complete only when DONE.", ""]
    d += table(["Measure", "Value"], [
        ["Tickets done", f"{len(done)} of {len(tickets)} ({pct(len(done), len(tickets))})"],
        ["Points done", f"{sum(t['points'] for t in done)} of {pts} ({pct(sum(t['points'] for t in done), pts)})"],
        ["Implemented and tested, awaiting review", status_count["IN REVIEW"]],
        ["Current wave", open_waves[0] if open_waves else "all waves complete"],
        ["Blocked", status_count["BLOCKED"]],
        ["Open P0 or P1 bugs", sum(1 for t in tickets if t["type"] == "bug" and t["status"] != "DONE" and t["priority"] in ("P0", "P1"))],
        ["Open security findings (verified weaknesses)", sum(1 for t in tickets if t["type"] == "security" and t["status"] != "DONE")],
        ["Last recorded test run", f"{tests['passed']} passed, {tests['failed']} failed" if tests else "none recorded"],
        ["Deployment", "Not deployed. No provider approved (BLK-003)"],
        ["Critical path remaining", f"{length} points: " + " → ".join(path)],
        ["Effort", "Estimates are in points; actual effort is not recorded"]])
    d += ["## By status", ""] + table(["Status", "Tickets"], [[s, status_count[s]] for s in STATUSES if status_count[s]])
    d += ["## By initiative", ""]
    rows = []
    for key, title in data["initiatives"].items():
        mine = [t for t in tickets if epics[t["epic"]]["initiative"] == key]
        if mine:
            rows.append([key, title, len(mine), sum(1 for t in mine if t["status"] == "DONE"), pct(sum(1 for t in mine if t["status"] == "DONE"), len(mine))])
        else:
            rows.append([key, title, 0, 0, "no ticket yet"])
    d += table(["Initiative", "Title", "Tickets", "Done", "Complete"], rows)
    d += ["## By wave (milestones)", ""] + table(["Wave", "Tickets", "Done", "In review", "Ready", "Blocked"], [
        [w, sum(1 for t in tickets if t["wave"] == w)] + [sum(1 for t in tickets if t["wave"] == w and t["status"] == s) for s in ("DONE", "IN REVIEW", "READY", "BLOCKED")]
        for w in sorted({t["wave"] for t in tickets})])
    d += ["## Blocked", ""] + table(["Ticket", "Title", "Reason"], [[t["id"], t["title"], t.get("blocked_reason", "")] for t in tickets if t["status"] == "BLOCKED"])
    d += ["## Owner decisions outstanding", ""] + [f"- {x}" for x in data.get("owner_decisions", [])] + [""]
    files["backlog/DASHBOARD.md"] = "\n".join(d)
    b = [note, "# Board", ""]
    for s in STATUSES:
        mine = [t for t in tickets if t["status"] == s]
        if mine:
            b += [f"## {s} ({len(mine)})", ""] + table(["Ticket", "Title", "Type", "Epic", "Wave", "Priority", "Points", "Depends on"], [
                [t["id"], t["title"], t["type"], t["epic"], t["wave"], t["priority"], t["points"], ", ".join(t["depends_on"]) or "—"] for t in mine])
    files["backlog/BOARD.md"] = "\n".join(b)
    dep = [note, "# Dependencies", "", f"Critical path of unfinished work: {length} points.", "", " → ".join(path), ""]
    dep += table(["Ticket", "Depends on", "Blocks"], [[t["id"], ", ".join(t["depends_on"]) or "—", ", ".join(o["id"] for o in tickets if t["id"] in o["depends_on"]) or "—"] for t in tickets])
    files["backlog/DEPENDENCIES.md"] = "\n".join(dep)
    cover: dict[str, list[str]] = {}
    for t in tickets:
        for r in t["requirements"]:
            cover.setdefault(r, []).append(t["id"])
    spec = json.loads((ROOT / "docs" / "spec" / "transition-data.json").read_text(encoding="utf-8"))
    known = [*spec["cloud_requirements"], *spec["requirements"]]
    tr = [note, "# Requirements traceability", "", "Requirement → tickets → evidence. Requirements come from `docs/spec/transition-data.json` (IR1.1's 100 requirements and the cloud requirements of CN1.1); addendum items are cited by their own identifiers.", ""]
    missing = [r for r in known if r not in cover and spec["requirements"].get(r, {}).get("impact") != "DEFERRED"]
    tr += [f"Covered by at least one ticket: {sum(1 for r in known if r in cover)} of {len(known)}. **Without a ticket yet: {len(missing)}** (listed at the end; later waves are elaborated as earlier ones finish).", ""]
    tr += table(["Requirement", "Tickets", "Status of those tickets", "Evidence"], [
        [r, ", ".join(ts), ", ".join(sorted({by_id[x]["status"] for x in ts})), "; ".join(by_id[x]["evidence"] for x in ts if by_id[x]["evidence"]) or "—"] for r, ts in sorted(cover.items())])
    tr += ["## Requirements with no ticket yet", "", ", ".join(missing) or "none", "", "## Finished tickets without evidence", "", ", ".join(t["id"] for t in tickets if t["status"] == "DONE" and not t["evidence"]) or "none", ""]
    files["backlog/TRACEABILITY.md"] = "\n".join(tr)
    for t in tickets:
        e = epics[t["epic"]]
        body = [note, f"# {t['id']} {t['title']}", ""]
        body += table(["Field", "Value"], [["Type", t["type"]], ["Initiative / epic", f"{e['initiative']} / {e['id']} {e['title']}"], ["Wave", t["wave"]], ["Priority", t["priority"]], ["Complexity (points)", t["points"]],
                                           ["Status", t["status"] + (f" — {t['blocked_reason']}" if t.get("blocked_reason") else "")], ["Depends on", ", ".join(t["depends_on"]) or "—"],
                                           ["Blocks", ", ".join(o["id"] for o in tickets if t["id"] in o["depends_on"]) or "—"], ["Requirements", ", ".join(t["requirements"]) or "—"], ["Architecture references", t["architecture"] or "—"]])
        body += ["## Objective", "", t["objective"], "", "## Scope", "", t["scope"], "", "## Acceptance criteria", ""] + [f"- [ ] {a}" for a in t["acceptance"]]
        body += ["", "## Test requirements", "", t["tests"], "", "## Deliverables", "", t["deliverables"], "", "## Definition of done", "", data["definition_of_done"], "", "## Risks", "", t["risks"], "", "## Evidence", "", t["evidence"] or "None yet.", ""]
        if not t.get("elaborated", True):
            body += ["> Outline ticket. It is elaborated (scope, interfaces, test cases) when its wave becomes current.", ""]
        files[f"backlog/tickets/{t['id']}.md"] = "\n".join(body)
    return files


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "validate"
    data = load()
    if cmd == "validate":
        errors = validate(data)
        print("\n".join(errors) if errors else f"backlog valid: {len(data['tickets'])} tickets, {len(data['epics'])} epics")
        return 1 if errors else 0
    if cmd == "render":
        files = render(data)
        if "--check" in argv:
            stale = [p for p, text in files.items() if not (ROOT / p).exists() or (ROOT / p).read_text(encoding="utf-8") != text + "\n"]
            print("stale: " + ", ".join(stale) if stale else "rendered files are current")
            return 1 if stale else 0
        (ROOT / "backlog" / "tickets").mkdir(parents=True, exist_ok=True)
        for p, text in files.items():
            (ROOT / p).write_text(text + "\n", encoding="utf-8")
        print(f"rendered {len(files)} files")
        return 0
    if cmd == "next":
        order = sorted((t for t in data["tickets"] if t["status"] == "READY"), key=lambda t: (t["priority"], t["wave"], t["id"]))
        print("\n".join(f"{t['id']} {t['priority']} wave {t['wave']} {t['points']}pt  {t['title']}" for t in order) or "nothing is READY")
        return 0
    if cmd == "set-status":
        tid, status = argv[2], argv[3]
        ticket = next(t for t in data["tickets"] if t["id"] == tid)
        ticket["status"] = status
        if "--evidence" in argv:
            ticket["evidence"] = argv[argv.index("--evidence") + 1]
        if "--reason" in argv:
            ticket["blocked_reason"] = argv[argv.index("--reason") + 1]
        refresh(data)
        errors = validate(data)
        if errors:
            print("\n".join(errors))
            return 1
        save(data)
        print(f"{tid} -> {status}")
        return 0
    if cmd == "record-tests":
        data["last_test_run"] = {"passed": int(argv[2]), "failed": int(argv[3])}
        save(data)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
