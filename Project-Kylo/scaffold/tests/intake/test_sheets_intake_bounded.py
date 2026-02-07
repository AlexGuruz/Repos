from services.intake.sheets_intake import build_bounded_range, find_last_ready_row, quote_tab_a1, values_to_csv


def test_quote_tab_a1_quotes_spaces():
    assert quote_tab_a1("JGD EXPENSES") == "'JGD EXPENSES'"
    assert quote_tab_a1("BANK") == "BANK"


def test_find_last_ready_row_skips_header_and_blanks():
    # Simulate values.get for A:A returning a 1-col matrix
    vals = [
        ["DATE"],  # header
        ["1/1/26"],
        [""],
        [None],
        ["1/5/26"],
        [""],
    ]
    assert find_last_ready_row(vals, header_rows=1) == 5


def test_find_last_ready_row_none_ready_returns_0():
    vals = [["DATE"], [""], [None], ["   "]]
    assert find_last_ready_row(vals, header_rows=1) == 0


def test_values_to_csv_quotes_commas_and_quotes():
    vals = [["A", "B"], ["hello,world", 'he said "hi"']]
    csv_text = values_to_csv(vals)
    assert csv_text.splitlines()[0] == "A,B"
    assert csv_text.splitlines()[1] == "\"hello,world\",\"he said \"\"hi\"\"\""


def test_build_bounded_range_quotes_tab_and_bounds():
    assert build_bounded_range("PETTY CASH", last_row=25, last_col="G") == "'PETTY CASH'!A1:G25"

