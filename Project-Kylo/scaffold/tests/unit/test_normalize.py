from services.common.normalize import normalize_description

def test_normalize_basic():
    assert normalize_description(" POS PURCHASE  #ATM LOAD!!! ") == "pos purchase atm load"
    assert normalize_description("Starbucks*1234") == "starbucks 1234"
    assert normalize_description(None) == ""
