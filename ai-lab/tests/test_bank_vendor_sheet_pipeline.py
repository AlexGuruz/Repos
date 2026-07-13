from __future__ import annotations

from pathlib import Path

from lib import google_sheets_client
from scripts import sheet_label_pipeline


def test_google_application_credentials_preflight(monkeypatch, tmp_path: Path) -> None:
    svc = tmp_path / "service-account.json"
    svc.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(svc))
    monkeypatch.delenv("GOOGLE_CREDENTIALS_FILE", raising=False)

    out = google_sheets_client.preflight_sheets_auth()

    assert out["ok"] is True
    assert out["service_account_file"] == str(svc)


def test_pipeline_skips_blank_source_rows_on_live_write(monkeypatch) -> None:
    writes: list[tuple[str, int, list[str]]] = []

    monkeypatch.setattr(sheet_label_pipeline, "validate_scope", lambda config: None)
    monkeypatch.setattr(sheet_label_pipeline, "load_alias_map", lambda path=None: {})
    monkeypatch.setattr(sheet_label_pipeline, "load_cleaning_rules", lambda path=None: {})

    import lib.google_sheets_client as sheets

    monkeypatch.setattr(sheets, "get_sheets_service", lambda: object())
    monkeypatch.setattr(sheets, "read_column_values", lambda *args, **kwargs: ["AMAZON MARKET", "", "SHELL OIL"])
    monkeypatch.setattr(sheets, "detect_formula_cells_in_range", lambda *args, **kwargs: [])

    def fake_write(service, spreadsheet_id, sheet_name, column, start_row, values):
        writes.append((column, start_row, values))
        return len(values)

    monkeypatch.setattr(sheets, "write_column_values", fake_write)

    report = sheet_label_pipeline.run_pipeline(
        sheet_label_pipeline.PipelineConfig(
            spreadsheet_id="sid",
            source_sheet_name="source",
            dest_sheet_name="dest",
            start_row=2,
            dry_run=False,
            approved=True,
        )
    )

    assert report["rows_processed"] == 2
    assert report["rows_written_c"] == 2
    assert [w[1] for w in writes] == [2, 2, 4, 4]
    assert 3 not in [w[1] for w in writes]
