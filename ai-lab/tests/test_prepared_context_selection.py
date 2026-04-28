from __future__ import annotations

import time
import uuid

import pytest

from brain.orchestrator.main import run
from brain.prepared_context.loader import try_prepared_context_answer
from brain.prepared_context.schema import PreparedSnapshot, now_iso
from brain.prepared_context.selection import select_snapshots_for_message
from brain.prepared_context.store import write_snapshot


def _minimal_snapshot(snapshot_type: str, confidence: float = 0.78) -> PreparedSnapshot:
    return PreparedSnapshot(
        snapshot_type=snapshot_type,
        generated_at=now_iso(),
        freshness_seconds=86400,
        source_files_or_tools=["test"],
        confidence=confidence,
        stale=False,
        errors=[],
        data={"ok": True},
        summary_short=f"{snapshot_type} test summary",
        summary_detailed="test",
        suggested_questions=[],
        evidence_items=[
            {
                "title": "t1",
                "source_path_or_tool": "test://a",
                "observed_at": now_iso(),
                "summary": "s",
                "confidence": 0.8,
            },
            {
                "title": "t2",
                "source_path_or_tool": "test://b",
                "observed_at": now_iso(),
                "summary": "s2",
                "confidence": 0.8,
            },
        ],
    )


@pytest.mark.parametrize(
    "msg,expect_substr",
    [
        ("what systems are active?", "system_snapshot"),
        ("anything broken in the lab?", "system_snapshot"),
        ("status of the lab", "system_snapshot"),
        ("which repos need cleanup?", "repo_pulse"),
        ("what are my next actions?", "project_agenda"),
        ("plan my day", "personal_ops_snapshot"),
        ("what is on my calendar today?", "personal_ops_snapshot"),
        ("growflow status", "growflow_snapshot"),
        ("transfer receipt status", "growflow_snapshot"),
        ("business automation status", "growflow_snapshot"),
        ("is the worker online?", "worker_snapshot"),
        ("ollama status on worker", "worker_snapshot"),
    ],
)
def test_paraphrase_selects_expected_snapshot(msg: str, expect_substr: str) -> None:
    sel = select_snapshots_for_message(msg, "answer")
    assert expect_substr in sel.snapshot_types, (msg, sel.snapshot_types, sel.scores)


def test_broad_lab_prompt_selects_trio() -> None:
    sel = select_snapshots_for_message("status of the lab", "answer")
    assert sel.broad_prompt is True
    for t in ("system_snapshot", "repo_pulse", "project_agenda"):
        assert t in sel.snapshot_types, sel.snapshot_types


def test_negative_no_growflow_for_generic_inventory() -> None:
    sel = select_snapshots_for_message("inventory levels at the warehouse", "answer")
    assert "growflow_snapshot" not in sel.snapshot_types


def test_negative_no_personal_ops_for_generic_work() -> None:
    sel = select_snapshots_for_message("work harder on the project", "answer")
    assert "personal_ops_snapshot" not in sel.snapshot_types


def test_negative_no_prepared_for_unrelated_trivia() -> None:
    sel = select_snapshots_for_message("who won the super bowl in 2024?", "answer")
    assert sel.snapshot_types == []


def test_time_sensitive_flag() -> None:
    assert select_snapshots_for_message("what is the current worker status?", "answer").time_sensitive is True


def test_selection_reasons_present() -> None:
    sel = select_snapshots_for_message("what systems are active?", "answer")
    assert "system_snapshot" in sel.reasons


def test_selection_runtime_under_10ms() -> None:
    t0 = time.perf_counter()
    for _ in range(200):
        select_snapshots_for_message("what systems are active? also repo docs stale", "answer")
    elapsed = (time.perf_counter() - t0) * 1000.0 / 200.0
    assert elapsed < 10.0, f"mean selection ms too slow: {elapsed:.3f}"


def test_quality_gate_still_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    write_snapshot(_minimal_snapshot("system_snapshot", confidence=0.4))
    ev = [
        {"title": "a", "source_path_or_tool": "s1", "observed_at": now_iso(), "summary": "x", "confidence": 0.5},
        {"title": "b", "source_path_or_tool": "s2", "observed_at": now_iso(), "summary": "y", "confidence": 0.5},
    ]
    monkeypatch.setattr(
        "brain.prepared_context.loader.load_snapshot_fresh",
        lambda name: {
            "snapshot_type": name,
            "generated_at": now_iso(),
            "freshness_seconds": 86400,
            "confidence": 0.4,
            "stale": False,
            "summary_short": "x",
            "evidence_items": ev,
            "data": {},
        }
        if name == "system_snapshot"
        else None,
    )
    out = try_prepared_context_answer("what systems are active?", "answer")
    assert out is not None
    assert "prepared_quality_score" in out or "prepared_quality_low" in out


def test_worker_not_called_when_prepared_worker_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    import brain.worker_health as wh

    def _boom(*args, **kwargs):
        raise AssertionError("live worker health must not run when prepared path answers")

    monkeypatch.setattr(wh, "get_worker_health_snapshot", _boom)
    write_snapshot(_minimal_snapshot("worker_snapshot", confidence=0.82))
    out = run(
        "is ollama up on the worker?",
        llm_base_url="",
        llm_model="",
        session_id=f"pc-sel-{uuid.uuid4().hex[:8]}",
    )
    assert "worker_snapshot" in out["reply"] or "ollama" in out["reply"].lower()


def test_company_bi_intent_boosts_growflow(monkeypatch: pytest.MonkeyPatch) -> None:
    write_snapshot(_minimal_snapshot("growflow_snapshot", confidence=0.8))
    monkeypatch.setattr(
        "brain.prepared_context.loader.load_snapshot_fresh",
        lambda name: {
            "snapshot_type": name,
            "generated_at": now_iso(),
            "freshness_seconds": 86400,
            "confidence": 0.8,
            "stale": False,
            "summary_short": "gf",
            "evidence_items": [
                {"title": "a", "source_path_or_tool": "x", "observed_at": now_iso(), "summary": "s", "confidence": 0.8},
                {"title": "b", "source_path_or_tool": "y", "observed_at": now_iso(), "summary": "s", "confidence": 0.8},
            ],
            "data": {},
        }
        if name == "growflow_snapshot"
        else None,
    )
    out = try_prepared_context_answer("sales and expenses overview", "company_bi")
    assert out is not None
    assert "growflow_snapshot" in (out.get("snapshot_types_used") or [])
