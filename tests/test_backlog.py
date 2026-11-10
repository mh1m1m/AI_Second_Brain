import copy

import backlog


def _data():
    return backlog.load()


def test_real_backlog_is_valid_and_acyclic():
    assert backlog.validate(_data()) == []


def test_cycle_is_detected():
    data = copy.deepcopy(_data())
    by_id = {t["id"]: t for t in data["tickets"]}
    by_id["SB-001"]["depends_on"] = ["SB-002"]
    assert any("cycle" in e for e in backlog.validate(data))


def test_done_without_evidence_and_ready_with_unmet_dependency_are_rejected():
    data = copy.deepcopy(_data())
    by_id = {t["id"]: t for t in data["tickets"]}
    by_id["SB-078"]["status"] = "DONE"
    errors = backlog.validate(data)
    assert any("SB-078" in e and "evidence" in e for e in errors)
    assert any("SB-078" in e and "dependencies" in e for e in errors)


def test_unknown_dependency_and_blocked_without_reason_are_rejected():
    data = copy.deepcopy(_data())
    by_id = {t["id"]: t for t in data["tickets"]}
    by_id["SB-010"]["depends_on"] = ["SB-999"]
    by_id["SB-011"]["status"], by_id["SB-011"]["blocked_reason"] = "BLOCKED", ""
    errors = backlog.validate(data)
    assert any("unknown dependency SB-999" in e for e in errors)
    assert any("BLOCKED without a reason" in e for e in errors)


def test_refresh_promotes_only_when_dependencies_are_satisfied():
    data = copy.deepcopy(_data())
    for t in data["tickets"]:
        t["status"], t["evidence"] = "BACKLOG", ""
    backlog.refresh(data)
    ready = {t["id"] for t in data["tickets"] if t["status"] == "READY"}
    assert ready == {t["id"] for t in data["tickets"] if not t["depends_on"]}


def test_rendering_is_deterministic_and_covers_every_ticket():
    data = _data()
    first, second = backlog.render(data), backlog.render(data)
    assert first == second
    assert all(f"backlog/tickets/{t['id']}.md" in first for t in data["tickets"])


def test_issue_payload_carries_labels_state_and_source_note():
    import github_mirror

    data = _data()
    pages = backlog.render(data)
    done = next(t for t in data["tickets"] if t["status"] == "DONE")
    body = github_mirror.payload(done, 3, pages)
    assert body["title"].startswith(done["id"]) and body["state"] == "closed" and body["milestone"] == 3
    assert f"priority: {done['priority']}" in body["labels"] and "backlog/backlog.json" in body["body"]


# --- review finding RV-02: every requirement is covered, deferred or excluded -----------------

def test_every_requirement_is_in_exactly_one_class_and_the_classes_add_up():
    from collections import Counter

    data, spec = _data(), backlog.load_spec()
    classes = backlog.classify_requirements(data, spec)
    count = Counter(classes.values())
    assert set(count) <= {"COVERED", "DEFERRED", "EXCLUDED"}
    assert count["COVERED"] + count["DEFERRED"] + count["EXCLUDED"] == len(backlog.known_requirements(spec)) == 148
    assert backlog.requirement_errors(data, spec) == []


def test_traceability_report_states_totals_that_add_up():
    import re

    report = backlog.render(_data())["backlog/TRACEABILITY.md"]
    number = {k: int(re.search(rf"\| {re.escape(k)} \| (\d+) \|", report).group(1)) for k in (
        "Covered by at least one ticket", "Deferred with justification", "Excluded with justification", "Unclassified or conflicting (must be 0)", "Total in the inventory")}
    assert number["Unclassified or conflicting (must be 0)"] == 0
    assert number["Covered by at least one ticket"] + number["Deferred with justification"] + number["Excluded with justification"] == number["Total in the inventory"]
    accepted, review, planned = map(int, re.search(r"(\d+) accepted .*?, (\d+) implemented and in review, (\d+) planned", report).groups())
    assert accepted + review + planned == number["Covered by at least one ticket"]


def test_a_requirement_without_ticket_or_disposition_is_rejected():
    data = copy.deepcopy(_data())
    for t in data["tickets"]:
        t["requirements"] = [r for r in t["requirements"] if r != "CR-10"]
    errors = backlog.validate(data)
    assert any("CR-10 has no ticket, deferral or exclusion" in e for e in errors)
    assert any("replacement CR-10 is not covered" in e for e in errors)  # an exclusion may not point at nothing


def test_bad_dispositions_and_unknown_requirements_are_rejected():
    data = copy.deepcopy(_data())
    by_id = {t["id"]: t for t in data["tickets"]}
    by_id["SB-010"]["requirements"].append("CR-99")
    by_id["SB-010"]["requirements"].append("FR-IMP-001")
    data["requirement_dispositions"]["NFR-004"] = {"disposition": "IGNORED", "reason": "no"}
    data["requirement_dispositions"]["XX-1"] = {"disposition": "DEFERRED", "reason": "a long enough justification text"}
    errors = backlog.validate(data)
    assert any("cites unknown requirement CR-99" in e for e in errors)
    assert any("FR-IMP-001 is cited by a ticket and also deferred" in e for e in errors)
    assert any("NFR-004: disposition must be one of" in e for e in errors)
    assert any("NFR-004: a deferral or exclusion needs a written justification" in e for e in errors)
    assert any("unknown requirement XX-1" in e for e in errors)


# --- review finding RV-03: provisional readiness is separate from security acceptance ---------

def _blank():
    data = copy.deepcopy(_data())
    for t in data["tickets"]:
        t["status"], t["evidence"] = "BACKLOG", ""
        t.pop("review", None)
    return data, {t["id"]: t for t in data["tickets"]}


def _set(by_id, status, *ids):
    for i in ids:
        by_id[i]["status"], by_id[i]["evidence"] = status, "test"


def test_ordinary_work_is_provisionally_ready_on_an_unreviewed_dependency_but_a_gate_is_not():
    data, by_id = _blank()
    by_id["X"] = {**copy.deepcopy(by_id["SB-001"]), "id": "X", "depends_on": ["SB-012"], "gate": "", "security_relevant": False}
    by_id["G"] = {**copy.deepcopy(by_id["SB-001"]), "id": "G", "depends_on": ["SB-012"], "gate": "security-integration", "security_relevant": False}
    data["tickets"] += [by_id["X"], by_id["G"]]
    _set(by_id, "DONE", "SB-001")
    _set(by_id, "IN REVIEW", "SB-012")
    backlog.refresh(data)
    assert by_id["X"]["status"] == "READY" and by_id["G"]["status"] == "BACKLOG"
    assert backlog.awaiting_review(by_id, "X") == ["SB-012"]
    assert "provisional until reviewed: SB-012" in backlog.readiness(by_id, by_id["X"])
    by_id["G"]["status"] = "READY"
    assert any("G: READY but a security-integration gate needs every dependency DONE: SB-012" in e for e in backlog.validate(data))


def test_real_gates_cannot_open_on_dependencies_that_are_only_in_review():
    data, by_id = _blank()
    gates = [t for t in data["tickets"] if t["gate"]]
    assert {t["id"] for t in gates} >= {"SB-055", "SB-056", "SB-058", "SB-060", "SB-070", "SB-071", "SB-078"}
    for t in data["tickets"]:
        if not t["gate"]:
            _set(by_id, "IN REVIEW", t["id"])
    backlog.refresh(data)
    assert all(t["status"] == "BACKLOG" for t in gates)
    gate = by_id["SB-055"]
    gate["status"] = "READY"
    assert any("SB-055" in e and "gate" in e for e in backlog.validate(data))


def test_a_gate_stays_closed_while_security_work_anywhere_beneath_it_is_unreviewed():
    data, by_id = _blank()
    assert "SB-010" in backlog.closure(by_id, "SB-055") and "SB-010" not in by_id["SB-055"]["depends_on"]
    for dep in backlog.closure(by_id, "SB-055"):
        _set(by_id, "DONE", dep)
        if by_id[dep]["security_relevant"]:
            by_id[dep]["review"] = {"reviewer": "A. Reviewer", "date": "2026-11-11", "reference": "review note 1"}
    _set(by_id, "IN REVIEW", "SB-010")
    by_id["SB-010"].pop("review")
    by_id["SB-055"]["status"] = "READY"
    errors = backlog.validate(data)
    assert any("SB-055: security-integration gate is open while security-relevant work awaits review: SB-010" in e for e in errors)
    assert any("DONE but dependencies are not DONE: SB-010" in e for e in errors)


def test_nothing_is_done_before_its_dependencies_and_security_work_needs_an_independent_review():
    data, by_id = _blank()
    _set(by_id, "DONE", "SB-001")
    _set(by_id, "IN REVIEW", "SB-003")
    _set(by_id, "DONE", "SB-092")
    assert any("SB-092: DONE but dependencies are not DONE: SB-003" in e for e in backlog.validate(data))
    data, by_id = _blank()
    _set(by_id, "DONE", "SB-001", "SB-012")
    assert any("SB-012: security-relevant and DONE without a recorded independent review" in e for e in backlog.validate(data))
    by_id["SB-012"]["review"] = {"reviewer": "claude code", "date": "2026-11-11", "reference": "self"}
    assert any("SB-012: the reviewer is the implementer" in e for e in backlog.validate(data))
    by_id["SB-012"]["review"] = {"reviewer": "A. Reviewer", "date": "2026-11-11", "reference": "review note 1"}
    assert any("SB-012: the reviewer is not one the owner designated" in e for e in backlog.validate(data))
    by_id["SB-012"]["review"]["reviewer"] = data["designated_reviewers"][0]
    assert not any("SB-012" in e for e in backlog.validate(data))
    data["designated_reviewers"] = []  # with nobody designated, any reviewer other than the implementer is accepted
    by_id["SB-012"]["review"]["reviewer"] = "A. Reviewer"
    assert not any("SB-012" in e for e in backlog.validate(data))


def test_acceptance_is_recorded_only_where_the_designated_reviewer_explicitly_gave_it():
    data = _data()
    assert data["designated_reviewers"] and not {x.casefold() for x in data["designated_reviewers"]} & {x.casefold() for x in data["implementers"]}
    by_id = {t["id"]: t for t in data["tickets"]}
    assert all(by_id[i]["status"] == "IN REVIEW" and "review" not in by_id[i] for i in ("SB-010", "SB-011"))  # accepted with conditions only
    review = by_id["SB-012"]["review"]
    assert by_id["SB-012"]["status"] == "DONE" and review["reviewer"] in data["designated_reviewers"]
    assert all(x in review["reference"] for x in ("canonical.py", "test_canonical.py", "does not cover SB-058"))
    for t in data["tickets"]:  # nobody else was accepted on the strength of this review
        assert "review" not in t or t["id"] == "SB-012"


def test_every_ticket_declares_security_relevance_and_gate():
    data = copy.deepcopy(_data())
    assert all(isinstance(t["security_relevant"], bool) and t["gate"] in backlog.GATES for t in data["tickets"])
    assert {"SB-010", "SB-011", "SB-012"} <= {t["id"] for t in data["tickets"] if t["security_relevant"]}
    del data["tickets"][0]["security_relevant"]
    data["tickets"][1]["gate"] = "maybe"
    errors = backlog.validate(data)
    assert sum("needs security_relevant" in e for e in errors) == 2


# --- review finding RV-04: every initiative and epic has work ---------------------------------

def test_every_initiative_and_epic_has_at_least_one_ticket():
    data = _data()
    epic_of = {e["id"]: e["initiative"] for e in data["epics"]}
    assert {epic_of[t["epic"]] for t in data["tickets"]} == set(data["initiatives"])
    assert {t["epic"] for t in data["tickets"]} == set(epic_of)
    for key in ("INIT-02", "INIT-12", "INIT-15"):
        assert sum(1 for t in data["tickets"] if epic_of[t["epic"]] == key) >= 3


def test_an_initiative_or_epic_without_tickets_is_rejected():
    data = copy.deepcopy(_data())
    data["initiatives"]["INIT-99"] = "Empty"
    data["epics"].append({"id": "EP-99", "title": "Empty", "initiative": "INIT-01"})
    errors = backlog.validate(data)
    assert "INIT-99: initiative has no ticket" in errors and "EP-99: epic has no ticket" in errors


# --- review finding RV-05: GitHub Issues cannot diverge silently ------------------------------

def _issue(number, view, extra_labels=()):
    return {"number": number, "title": view["title"], "state": view["state"], "body": view["body"].replace("\n", "\r\n") + "\r\n",
            "labels": [{"name": x} for x in [*view["labels"], *extra_labels]], "milestone": {"title": view["milestone"]}}


def _mirror_state():
    import github_mirror as gm

    data = _data()
    pages = backlog.render(data)
    views = {t["id"]: gm.expected_view(t, pages) for t in data["tickets"]}
    mapping = {tid: {"issue": n, "pushed": gm.fingerprint(v)} for n, (tid, v) in enumerate(views.items(), start=1)}
    issues = [_issue(mapping[tid]["issue"], v) for tid, v in views.items()]
    return gm, data, pages, mapping, issues


def test_no_drift_when_github_holds_what_was_pushed():
    gm, data, pages, mapping, issues = _mirror_state()
    issues[0]["labels"].append({"name": "good first issue"})  # labels the mirror does not manage are left alone
    issues[1]["body"] += "\r\n\r\n---\r\n_Generated by [Claude Code](https://claude.ai/code)_"  # footer added by the session proxy
    issues.append({"number": 900, "title": "RV-01 review finding", "state": "open", "body": "", "labels": [], "milestone": None})
    issues.append({"number": 901, "title": "SB-001 looks like a ticket", "state": "open", "body": "", "labels": [], "milestone": None, "pull_request": {}})
    assert gm.drift(data, pages, mapping, issues) == []
    assert gm.pending(data, pages, mapping) == []


def test_edits_made_on_github_are_reported_field_by_field():
    gm, data, pages, mapping, issues = _mirror_state()
    by_number = {i["number"]: i for i in issues}
    by_number[mapping["SB-010"]["issue"]]["state"] = "closed"
    by_number[mapping["SB-011"]["issue"]]["labels"] = [{"name": "status: done"}]
    by_number[mapping["SB-012"]["issue"]]["title"] = "SB-012 approved"
    by_number[mapping["SB-020"]["issue"]]["body"] += "edited"
    by_number[mapping["SB-032"]["issue"]]["milestone"] = None
    issues.remove(by_number[mapping["SB-051"]["issue"]])
    issues.append({"number": 950, "title": "SB-999 made by hand", "state": "open", "body": "", "labels": [], "milestone": None})
    report = "\n".join(gm.drift(data, pages, mapping, issues))
    for expected in ("SB-010: issue #", "(state)", "SB-011", "(labels)", "SB-012", "(title)", "SB-020", "(body)", "SB-032", "(milestone)",
                     "SB-051: issue #", "is missing on GitHub", "issue #950 'SB-999 made by hand' looks like a ticket but is not in the backlog"):
        assert expected in report
    assert len(gm.drift(data, pages, mapping, issues)) == 7


def test_a_backlog_change_that_was_not_pushed_is_reported_offline():
    gm, data, pages, mapping, _ = _mirror_state()
    changed = copy.deepcopy(data)
    next(t for t in changed["tickets"] if t["id"] == "SB-020")["status"] = "IN PROGRESS"
    del mapping["SB-032"]
    mapping["SB-998"] = {"issue": 998, "pushed": "x"}
    assert gm.pending(changed, backlog.render(changed), mapping) == ["SB-020", "SB-032", "SB-998 (no longer in the backlog)"]


def test_the_committed_mirror_record_matches_the_committed_backlog():
    # Fails when backlog.json changed and `tools/github_mirror.py OWNER/REPO` was not run before committing.
    import github_mirror as gm

    data = _data()
    assert gm.pending(data, backlog.render(data), gm.load_map()) == []


def test_labels_carry_gate_and_security_review_markers():
    import github_mirror as gm

    data = _data()
    by_id = {t["id"]: t for t in data["tickets"]}
    assert "gate: security-integration" in gm.labels_for(by_id["SB-055"]) and "review: security" in gm.labels_for(by_id["SB-055"])
    assert "gate: release" in gm.labels_for(by_id["SB-071"])
    assert all(gm.managed(x) for t in data["tickets"] for x in gm.labels_for(t)) and not gm.managed("good first issue")


def test_an_issue_pushed_from_another_branch_is_a_note_but_an_edit_to_it_is_drift():
    gm, data, pages, mapping, issues = _mirror_state()
    other = copy.deepcopy(data)
    ticket = next(t for t in other["tickets"] if t["id"] == "SB-020")
    ticket["status"] = "IN PROGRESS"
    pushed = gm.payload(ticket, 1, backlog.render(other))
    assert gm.marker(pushed["body"]) == gm.fingerprint(gm.expected_view(ticket, backlog.render(other)))
    issue = next(i for i in issues if i["number"] == mapping["SB-020"]["issue"])
    issue["body"] = pushed["body"] + "\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_"
    issue["labels"] = [{"name": x} for x in pushed["labels"]]
    assert gm.drift(data, pages, mapping, issues) == [] and gm.elsewhere(data, mapping, issues) == ["SB-020"]
    issue["state"] = "closed"  # a person closes it: the marker no longer matches the content
    assert any("SB-020" in line and "changed on GitHub" in line for line in gm.drift(data, pages, mapping, issues))
    assert gm.elsewhere(data, mapping, issues) == []


def test_the_marker_is_hidden_text_and_does_not_change_the_fingerprint():
    gm, data, pages, _, _ = _mirror_state()
    ticket = data["tickets"][0]
    body = gm.payload(ticket, 1, pages)["body"]
    assert body.rstrip().endswith("-->") and gm.marker(body) == gm.fingerprint(gm.expected_view(ticket, pages))
    assert gm.marker("no marker here") == ""
