from scaffold.tools.importer import normalize_row, parse_date, normalize_amount_expr, stable_hash


def test_parse_date_variants():
    assert parse_date("2/19/25") == "2025-02-19"
    assert parse_date("12/25/2025") == "2025-12-25"
    assert parse_date(None) is None


def test_normalize_amount_expr_money_formats():
    assert normalize_amount_expr("$ 799.07") == "=799.07"
    assert normalize_amount_expr("$ (300.00)") == "=-300.00"
    assert normalize_amount_expr(120) == "=120.00"


def test_hash_idempotent_on_whitespace_and_case():
    row_a = {
        "Date": "2/19/25",
        "Source": " Coffee Shop ",
        "Company_ID": "710",
        "Amount": "$ 12.34",
        "Target_Sheet": " Cash ",
        "Target_Header": "Food",
        "Match_Notes": "lunch",
        "Approved": "TRUE",
    }
    row_b = {
        "Date": " 2/19/25 ",
        "Source": "coffee shop",
        "Company_ID": " 710 ",
        "Amount": "$12.34",
        "Target_Sheet": "Cash",
        "Target_Header": "Food ",
        "Match_Notes": " lunch ",
        "Approved": "true",
    }
    na = normalize_row(row_a, "710")
    nb = normalize_row(row_b, "710")
    assert stable_hash(na) == stable_hash(nb)


