import pytest

from app.services.barcode_allocation import validate_barcode_format


def test_validate_barcode_accepts_internal_style() -> None:
    validate_barcode_format("2001234567890")


def test_validate_barcode_accepts_short_alnum() -> None:
    validate_barcode_format("A1")


def test_validate_barcode_rejects_space() -> None:
    with pytest.raises(ValueError, match="Barcode"):
        validate_barcode_format("hello world")


def test_validate_barcode_rejects_leading_dot() -> None:
    with pytest.raises(ValueError, match="Barcode"):
        validate_barcode_format(".abc")


def test_validate_barcode_rejects_too_long() -> None:
    with pytest.raises(ValueError, match="128"):
        validate_barcode_format("a" + "b" * 128)
