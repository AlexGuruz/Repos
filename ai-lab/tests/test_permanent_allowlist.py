from __future__ import annotations

from brain import permanent_allowlist as pa


def test_add_find_and_delete_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "PERMANENT_ALLOWLIST_PATH", tmp_path / "permanent_allowlist.json")

    rule = pa.add_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "ignored_empty": ""},
        note="from test",
        source_approval_id="APR-1",
    )

    assert rule["id"].startswith("PAR-")
    assert rule["match"] == {"script_path": "registry/foo.py"}
    assert pa.find_matching_rule("run_approved", {"script_path": "registry/foo.py"})["id"] == rule["id"]
    assert pa.find_matching_rule("run_approved", {"script_path": "registry/bar.py"}) is None

    assert pa.delete_rule(rule["id"]) is True
    assert pa.find_matching_rule("run_approved", {"script_path": "registry/foo.py"}) is None


def test_never_permanent_actions_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "PERMANENT_ALLOWLIST_PATH", tmp_path / "permanent_allowlist.json")

    try:
        pa.add_rule("restart_service", {"target": "backend"})
    except ValueError as exc:
        assert "cannot be permanently allowlisted" in str(exc)
    else:
        raise AssertionError("restart_service should not be permanently allowlisted")

    assert pa.find_matching_rule("restart_service", {"target": "backend"}) is None


def test_brain_spec_match_payload_uses_stable_subset():
    payload = pa.brain_spec_match_payload(
        {
            "file_path": "/repo/a.py",
            "action_type": "manual_enqueue",
            "created_at": "ignored",
            "payload": {"script_path": "registry/foo.py"},
        }
    )

    assert payload == {
        "file_path": "/repo/a.py",
        "script_path": "registry/foo.py",
        "action_type": "manual_enqueue",
    }
