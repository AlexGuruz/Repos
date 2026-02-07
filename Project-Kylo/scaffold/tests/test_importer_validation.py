from scaffold.tools.importer import normalize_row, validate_row


def test_validation_missing_fields_and_company_mismatch():
    raw = {
        "Date": "2/19/25",
        "Source": "",
        "Company_ID": "999",
        "Amount": "$ 10.00",
        "Target_Sheet": "",
        "Target_Header": "",
        "Match_Notes": "",
        "Approved": "FALSE",
    }
    norm = normalize_row(raw, "710")
    errs = validate_row(norm, "710")
    codes = {c for (c, _m) in errs}
    assert "NOT_APPROVED" in codes
    assert "COMPANY_MISMATCH" in codes
    assert "SOURCE_EMPTY" in codes
    assert "TARGET_SHEET_EMPTY" in codes
    assert "TARGET_HEADER_EMPTY" in codes


