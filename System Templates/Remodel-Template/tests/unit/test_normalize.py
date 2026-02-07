"""
Unit tests for text normalization utilities.
"""
from yourapp.common.normalize import normalize_description


def test_normalize_basic():
    """Test basic normalization functionality."""
    assert normalize_description(" POS PURCHASE  #ATM LOAD!!! ") == "pos purchase atm load"
    assert normalize_description("Test*1234") == "test 1234"
    assert normalize_description(None) == ""


def test_normalize_empty():
    """Test normalization of empty strings."""
    assert normalize_description("") == ""
    assert normalize_description("   ") == ""


def test_normalize_special_chars():
    """Test normalization removes special characters."""
    assert normalize_description("test@example.com") == "test example com"
    assert normalize_description("item-123_price") == "item 123 price"
