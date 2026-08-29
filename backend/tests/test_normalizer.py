"""ANPR normalisation & validation tests."""
from app.ai.anpr.normalizer import is_valid_plate, normalize_plate


def test_valid_standard_plate():
    r = normalize_plate("GJ01AB1234")
    assert r.normalized == "GJ01AB1234"
    assert r.valid_format is True


def test_lowercase_and_spaces():
    r = normalize_plate("gj 01 ab 1234")
    assert r.normalized == "GJ01AB1234"
    assert r.valid_format is True


def test_noise_stripped():
    r = normalize_plate("*GJ-01-AB-1234!")
    assert r.normalized == "GJ01AB1234"
    assert r.valid_format is True


def test_position_aware_coercion():
    # OCR confusions: O->0 in digit slot, 8->B in letter slot
    r = normalize_plate("GJO1AB1234")   # 'O' where a digit is expected
    assert r.normalized == "GJ01AB1234"
    assert r.valid_format is True


def test_single_digit_rto():
    r = normalize_plate("GJ1AB1234")
    assert r.valid_format is True


def test_bh_series():
    r = normalize_plate("22BH1234AA")
    assert r.valid_format is True


def test_invalid_plate_flagged_not_dropped():
    r = normalize_plate("XYZ")
    assert r.valid_format is False
    assert r.normalized == "XYZ"          # raw content preserved, just flagged


def test_is_valid_helper():
    assert is_valid_plate("GJ05CD7890") is True
    assert is_valid_plate("HELLO") is False


def test_empty_input():
    r = normalize_plate("")
    assert r.normalized == ""
    assert r.valid_format is False
