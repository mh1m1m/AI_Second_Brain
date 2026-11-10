#!/usr/bin/env python3
"""Backlog tool. `backlog/backlog.json` is the source of truth; everything else under `backlog/` is generated from it.

    python tools/backlog.py validate | render [--check] | next
    python tools/backlog.py set-status SB-NNN STATUS [--evidence TEXT] [--reason TEXT] [--reviewer NAME --review-ref TEXT]
    python tools/backlog.py record-tests PASSED FAILED

Rules enforced here are described in backlog/README.md: dependency readiness and security gates, requirement
dispositions, initiative coverage.

Standard library only. This is project tooling, not part of the service.
"""
from __future__ import annotations

import datetime
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backlog" / "backlog.json"
STATUSES = ["BACKLOG", "READY", "IN PROGRESS", "IN REVIEW", "TESTING", "BLOCKED", "DONE", "REOPENED"]
SATISFIED = {"DONE", "IN REVIEW"}  # enough to start ordinary work provisionally; never enough for a gate or for DONE
STARTED = ("READY", "IN PROGRESS", "IN REVIEW", "TESTING")
GATES = ["", "security-integration", "release"]
DISPOSITIONS = ["DEFERRED", "EXCLUDED"]
SPEC = ROOT / "docs" / "spec" / "transition-data.json"
PRIORITIES = ["P0", "P1", "P2", "P3"]
TYPES = ["epic", "feature", "task", "bug", "security", "research", "debt"]


def load(path: Path = SRC) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(data: dict, path: Path = SRC) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_spec(path: Path = SPEC) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def known_requirements(spec: dict) -> list[str]:
    return [*spec["cloud_requirements"], *spec["requirements"]]


def classify_requirements(data: dict, spec: dict) -> dict[str, str]:
    """Every requirement in the inventory is COVERED, DEFERRED or EXCLUDED; anything else is an error."""
    cited = {r for t in data["tickets"] for r in t["requirements"]}
    recorded = data.get("requirement_dispositions", {})
    out: dict[str, str] = {}
    for req in known_requirements(spec):
        if req in cited and req in recorded:
            out[req] = "CONFLICT"
        elif req in cited:
            out[req] = "COVERED"
        elif recorded.get(req, {}).get("disposition") in DISPOSITIONS:
            out[req] = recorded[req]["disposition"]
        else:
            out[req] = "UNCLASSIFIED"
    return out


def requirement_errors(data: dict, spec: dict) -> list[str]:
    errors: list[str] = []
    known = known_requirements(spec)
    errors += [f"requirement inventory lists {r} more than once" for r, n in Counter(known).items() if n > 1]
    classes = classify_requirements(data, spec)
    for t in data["tickets"]:
        errors += [f"{t['id']}: cites unknown requirement {r}" for r in t["requirements"] if r not in classes]
    for req, kind in classes.items():
        if kind == "UNCLASSIFIED":
            errors.append(f"requirement {req} has no ticket, deferral or exclusion")
        elif kind == "CONFLICT":
            errors.append(f"requirement {req} is cited by a ticket and also deferred or excluded")
    for req, entry in data.get("requirement_dispositions", {}).items():
        if req not in classes:
            errors.append(f"disposition recorded for unknown requirement {req}")
        if entry.get("disposition") not in DISPOSITIONS:
            errors.append(f"requirement {req}: disposition must be one of {', '.join(DISPOSITIONS)}")
        if len(entry.get("reason", "").strip()) < 20:
            errors.append(f"requirement {req}: a deferral or exclusion needs a written justification")
        for other in entry.get("replaced_by", []):
            if classes.get(other) != "COVERED":
                errors.append(f"requirement {req}: replacement {other} is not covered by a ticket")
    if sum(Counter(classes.values())[k] for k in ("COVERED", *DISPOSITIONS)) != len(set(known)) and not errors:
        errors.append("requirement classes do not add up to the inventory")
    return errors


def closure(tickets: dict[str, dict], tid: str) -> list[str]:
    """Every ticket this one depends on, directly or through others."""
    seen: dict[str, None] = {}
    stack = list(tickets[tid]["depends_on"])
    while stack:
        dep = stack.pop()
        if dep in tickets and dep not in seen:
            seen[dep] = None
            stack.extend(tickets[dep]["depends_on"])
    return sorted(seen)


def awaiting_review(tickets: dict[str, dict], tid: str) -> list[str]:
    """Security-relevant work this ticket is built on that has not been reviewed and accepted (DONE)."""
    return [d for d in closure(tickets, tid) if tickets[d].get("security_relevant") and tickets[d]["status"] != "DONE"]


def dependencies_met(tickets: dict[str, dict], t: dict) -> bool:
    """Ordinary work may start on dependencies that are DONE or IN REVIEW. A gate needs every dependency DONE."""
    enough = {"DONE"} if t.get("gate") else SATISFIED
    return all(tickets[d]["status"] in enough for d in t["depends_on"] if d in tickets)


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


def validate(data: dict, spec: dict | None = None) -> list[str]:
    errors: list[str] = []
    implementers = {x.casefold() for x in data.get("implementers", [])}
    designated = {x.casefold() for x in data.get("designated_reviewers", [])}
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
        if t.get("gate", "") not in GATES or not isinstance(t.get("security_relevant"), bool):
            errors.append(f"{tid}: needs security_relevant (true or false) and gate (one of {GATES})")
            continue
        known_deps = [d for d in t["depends_on"] if d in tickets]
        if t["status"] in STARTED and not dependencies_met(tickets, t):
            enough = {"DONE"} if t["gate"] else SATISFIED
            unmet = [d for d in known_deps if tickets[d]["status"] not in enough]
            rule = f"a {t['gate']} gate needs every dependency DONE" if t["gate"] else "dependencies not satisfied"
            errors.append(f"{tid}: {t['status']} but {rule}: {', '.join(unmet)}")
        if t["status"] == "DONE":
            unmet = [d for d in known_deps if tickets[d]["status"] != "DONE"]
            if unmet:
                errors.append(f"{tid}: DONE but dependencies are not DONE: {', '.join(unmet)}")
        if t["gate"] and t["status"] in (*STARTED, "DONE"):
            pending = awaiting_review(tickets, tid)
            if pending:
                errors.append(f"{tid}: {t['gate']} gate is open while security-relevant work awaits review: {', '.join(pending)}")
        if t["security_relevant"] and t["status"] == "DONE":
            review = t.get("review") or {}
            if not all(str(review.get(k, "")).strip() for k in ("reviewer", "date", "reference")):
                errors.append(f"{tid}: security-relevant and DONE without a recorded independent review (reviewer, date, reference)")
            elif review["reviewer"].casefold() in implementers:
                errors.append(f"{tid}: the reviewer is the implementer; an independent review is required (PD-004)")
            elif designated and review["reviewer"].casefold() not in designated:
                errors.append(f"{tid}: the reviewer is not one the owner designated ({', '.join(data['designated_reviewers'])})")
    for e in data["epics"]:
        if e["initiative"] not in data["initiatives"]:
            errors.append(f"{e['id']}: unknown initiative {e['initiative']}")
        if not any(t["epic"] == e["id"] for t in data["tickets"]):
            errors.append(f"{e['id']}: epic has no ticket")
    covered = {e["initiative"] for e in data["epics"] if any(t["epic"] == e["id"] for t in data["tickets"])}
    errors += [f"{key}: initiative has no ticket" for key in data["initiatives"] if key not in covered]
    errors += requirement_errors(data, spec if spec is not None else load_spec())
    cycle = find_cycle(tickets)
    if cycle:
        errors.append("dependency cycle: " + " -> ".join(cycle))
    return errors


def refresh(data: dict) -> None:
    """BACKLOG becomes READY when its dependencies allow it (see dependencies_met), and the reverse."""
    tickets = {t["id"]: t for t in data["tickets"]}
    for t in data["tickets"]:
        met = dependencies_met(tickets, t)
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


def readiness(by_id: dict[str, dict], t: dict) -> str:
    pending = awaiting_review(by_id, t["id"])
    if t["status"] == "DONE" or not pending:
        return "—"
    word = "held until reviewed" if t.get("gate") else "provisional until reviewed"
    return f"{word}: {', '.join(pending)}"


def render(data: dict, spec: dict | None = None) -> dict[str, str]:
    tickets = data["tickets"]
    by_id = {t["id"]: t for t in tickets}
    spec = spec if spec is not None else load_spec()
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
        ["Security-relevant tickets awaiting independent review", ", ".join(t["id"] for t in tickets if t["security_relevant"] and t["status"] == "IN REVIEW") or "none"],
        ["Ready only provisionally (built on unreviewed security work)", ", ".join(t["id"] for t in tickets if t["status"] in STARTED and not t["gate"] and awaiting_review(by_id, t["id"])) or "none"],
        ["Gates open", ", ".join(t["id"] for t in tickets if t["gate"] and t["status"] in (*STARTED, "DONE")) or "none"],
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
        rows.append([key, title, ", ".join(e["id"] for e in data["epics"] if e["initiative"] == key), len(mine), sum(1 for t in mine if t["status"] == "DONE"), pct(sum(1 for t in mine if t["status"] == "DONE"), len(mine))])
    d += table(["Initiative", "Title", "Epics", "Tickets", "Done", "Complete"], rows)
    d += ["## Gates", "", "A gate becomes READY only when every dependency is DONE, which includes independent review of every security-relevant ticket beneath it.", ""]
    d += table(["Gate", "Kind", "Title", "Status", "Dependencies not yet DONE", "Security-relevant work beneath it not yet accepted"], [
        [t["id"], t["gate"], t["title"], t["status"], ", ".join(x for x in t["depends_on"] if by_id[x]["status"] != "DONE") or "—", ", ".join(awaiting_review(by_id, t["id"])) or "—"]
        for t in tickets if t["gate"]])
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
            b += [f"## {s} ({len(mine)})", ""] + table(["Ticket", "Title", "Type", "Epic", "Wave", "Priority", "Points", "Depends on", "Security", "Gate", "Readiness"], [
                [t["id"], t["title"], t["type"], t["epic"], t["wave"], t["priority"], t["points"], ", ".join(t["depends_on"]) or "—",
                 "review required" if t["security_relevant"] else "—", t["gate"] or "—", readiness(by_id, t)] for t in mine])
    files["backlog/BOARD.md"] = "\n".join(b)
    dep = [note, "# Dependencies", "", f"Critical path of unfinished work: {length} points.", "", " → ".join(path), ""]
    dep += table(["Ticket", "Depends on", "Blocks"], [[t["id"], ", ".join(t["depends_on"]) or "—", ", ".join(o["id"] for o in tickets if t["id"] in o["depends_on"]) or "—"] for t in tickets])
    files["backlog/DEPENDENCIES.md"] = "\n".join(dep)
    cover: dict[str, list[str]] = {}
    for t in tickets:
        for r in t["requirements"]:
            cover.setdefault(r, []).append(t["id"])
    known = known_requirements(spec)
    classes = classify_requirements(data, spec)
    count = Counter(classes.values())
    recorded = data.get("requirement_dispositions", {})
    notes = data.get("requirement_notes", {})

    def progress(req: str) -> str:
        states = {by_id[x]["status"] for x in cover[req]}
        return "accepted" if states == {"DONE"} else "implemented, in review" if states <= {"DONE", "IN REVIEW"} else "planned"

    stage = Counter(progress(r) for r in known if classes[r] == "COVERED")
    tr = [note, "# Requirements traceability", "", "Requirement → tickets → evidence. The inventory is `docs/spec/transition-data.json`: the 100 requirements of IR1.1 and the 48 cloud requirements of CN1.1. "
          "Every requirement is in exactly one class; `tools/backlog.py validate` fails otherwise. Covered means a ticket is responsible for it, not that it is built.", ""]
    tr += table(["Class", "Requirements"], [
        ["Covered by at least one ticket", count["COVERED"]], ["Deferred with justification", count["DEFERRED"]], ["Excluded with justification", count["EXCLUDED"]],
        ["Unclassified or conflicting (must be 0)", count["UNCLASSIFIED"] + count["CONFLICT"]], ["Total in the inventory", len(known)]])
    tr += [f"Of the {count['COVERED']} covered: {stage['accepted']} accepted (every ticket DONE), {stage['implemented, in review']} implemented and in review, {stage['planned']} planned.", ""]
    tr += ["## Covered", ""] + table(["Requirement", "Tickets", "Progress", "Status of those tickets", "Evidence", "Note"], [
        [r, ", ".join(cover[r]), progress(r), ", ".join(sorted({by_id[x]["status"] for x in cover[r]})), "; ".join(by_id[x]["evidence"] for x in cover[r] if by_id[x]["evidence"]) or "—", notes.get(r, "—")]
        for r in sorted(known) if classes[r] == "COVERED"])
    for kind, title in (("DEFERRED", "Deferred"), ("EXCLUDED", "Excluded")):
        tr += [f"## {title}", ""] + table(["Requirement", "Justification", "Replaced by", "Revisit"], [
            [r, recorded[r]["reason"], ", ".join(recorded[r].get("replaced_by", [])) or "—", recorded[r].get("revisit", "—")] for r in sorted(known) if classes[r] == kind])
    tr += ["## Finished tickets without evidence", "", ", ".join(t["id"] for t in tickets if t["status"] == "DONE" and not t["evidence"]) or "none", ""]
    files["backlog/TRACEABILITY.md"] = "\n".join(tr)
    for t in tickets:
        e = epics[t["epic"]]
        body = [note, f"# {t['id']} {t['title']}", ""]
        body += table(["Field", "Value"], [["Type", t["type"]], ["Initiative / epic", f"{e['initiative']} / {e['id']} {e['title']}"], ["Wave", t["wave"]], ["Priority", t["priority"]], ["Complexity (points)", t["points"]],
                                           ["Security-relevant", "yes: stops at IN REVIEW until independently reviewed (PD-004)" if t["security_relevant"] else "no"],
                                           ["Gate", f"{t['gate']}: READY only when every dependency is DONE" if t["gate"] else "no"], ["Readiness", readiness(by_id, t)],
                                           ["Independent review", "{reviewer}, {date}, {reference}".format(**t["review"]) if t.get("review") else "—"],
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
        by_id = {t["id"]: t for t in data["tickets"]}
        for t in order:
            pending = awaiting_review(by_id, t["id"])
            print(f"{t['id']} {t['priority']} wave {t['wave']} {t['points']}pt  {t['title']}" + (f"  [provisional: awaits review of {', '.join(pending)}]" if pending else ""))
        if not order:
            print("nothing is READY")
        return 0
    if cmd == "set-status":
        tid, status = argv[2], argv[3]
        ticket = next(t for t in data["tickets"] if t["id"] == tid)
        ticket["status"] = status
        if "--evidence" in argv:
            ticket["evidence"] = argv[argv.index("--evidence") + 1]
        if "--reason" in argv:
            ticket["blocked_reason"] = argv[argv.index("--reason") + 1]
        if "--reviewer" in argv and "--review-ref" in argv:
            ticket["review"] = {"reviewer": argv[argv.index("--reviewer") + 1], "date": datetime.date.today().isoformat(), "reference": argv[argv.index("--review-ref") + 1]}
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
