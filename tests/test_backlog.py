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
