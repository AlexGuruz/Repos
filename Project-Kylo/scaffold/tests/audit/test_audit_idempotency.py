from __future__ import annotations

from services.audit.notes import write_audit_notes
from services.audit.row_model import ChangeEvent
from services.audit.tick import _filter_new_events, _save_emitted_signatures


def _event(*, ts: str = "2026-08-14T00:00:00Z") -> ChangeEvent:
    return ChangeEvent(
        ts=ts,
        event="ANOMALY",
        row_key="sid|BANK|2",
        source_spreadsheet_id="sid",
        source_tab="BANK",
        sheet_row=3,
        company_id="JGD",
        changed_field="payroll_pair",
        before="FROM_BANK",
        after="paired_row=4",
        anomalies=["FROM_BANK_PAIR", "FALSE_PAYROLL"],
        posted_date="2026-08-14",
        description="FROM BANK",
        amount_cents=10000,
        txn_uid="txn-1",
        business_line_uid="bl-1",
    )


def test_filter_new_events_suppresses_previously_emitted_signature(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    first, signatures, changed = _filter_new_events("JGD_2026", [_event(ts="2026-08-14T00:00:00Z")])
    assert len(first) == 1
    assert changed is True
    _save_emitted_signatures(tmp_path / ".kylo/instances/JGD_2026/state/audit_emitted_events.json", signatures)

    second, _signatures, changed_again = _filter_new_events("JGD_2026", [_event(ts="2026-08-14T00:05:00Z")])
    assert second == []
    assert changed_again is False


class _Request:
    def __init__(self, callback):
        self._callback = callback

    def execute(self):
        return self._callback()


class _Values:
    def __init__(self, notes: dict[str, str], updates: list[dict]):
        self._notes = notes
        self._updates = updates

    def batchGet(self, *, spreadsheetId, ranges):
        def _do():
            value_ranges = []
            for rng in ranges:
                cell = rng.split("!")[-1]
                value = self._notes.get(cell, "")
                value_ranges.append({"range": rng, "values": [[value]] if value else []})
            return {"valueRanges": value_ranges}

        return _Request(_do)

    def batchUpdate(self, *, spreadsheetId, body):
        def _do():
            self._updates.append(body)
            for item in body.get("data", []):
                cell = str(item.get("range", "")).split("!")[-1]
                values = item.get("values") or []
                self._notes[cell] = str(values[0][0]) if values and values[0] else ""
            return {}

        return _Request(_do)


class _Spreadsheets:
    def __init__(self, notes: dict[str, str], updates: list[dict]):
        self._values = _Values(notes, updates)

    def values(self):
        return self._values


class _Service:
    def __init__(self, notes: dict[str, str], updates: list[dict]):
        self._spreadsheets = _Spreadsheets(notes, updates)

    def spreadsheets(self):
        return self._spreadsheets


def test_write_audit_notes_skips_event_already_present_in_manual_note():
    notes = {"G3": "manual reviewer context"}
    updates: list[dict] = []
    service = _Service(notes, updates)

    assert write_audit_notes(service, [_event()], note_column="G") == 1
    first_note = notes["G3"]
    assert "manual reviewer context" in first_note
    assert "KYLO-AUDIT-SYSTEM" in first_note

    assert write_audit_notes(service, [_event(ts="2026-08-14T00:05:00Z")], note_column="G") == 0
    assert notes["G3"] == first_note
    assert len(updates) == 1
