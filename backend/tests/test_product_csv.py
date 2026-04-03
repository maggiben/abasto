from decimal import Decimal

from app.services.product_csv import CSV_COLUMNS, parse_import_csv, products_to_csv_bytes


def test_parse_roundtrip_minimal() -> None:
    header = ",".join(CSV_COLUMNS)
    row = "1,Test,,10.00,,,bc123,,,,false,true,5,"
    text = header + "\n" + row + "\n"
    rows, errors = parse_import_csv(text)
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r.id == 1
    assert r.name == "Test"
    assert r.price == Decimal("10")
    assert r.barcode == "bc123"
    assert r.quantity == Decimal("5")
    assert r.is_active is True


def test_products_to_csv_bytes_empty() -> None:
    b = products_to_csv_bytes([])
    assert CSV_COLUMNS[0].encode() in b


def test_parse_catalog_semicolon() -> None:
    text = (
        "ean;producto;brand;cat1;cat2;cat3\n"
        '4894947016844;Celular tecno;Tecno;Electro;Celulares;Libres\n'
    )
    rows, errors = parse_import_csv(text)
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r.id is None
    assert r.barcode == "4894947016844"
    assert r.name == "Celular tecno"
    assert r.price == Decimal("0")
    assert r.quantity == Decimal("0")
    assert r.is_active is True
    assert "Tecno" in (r.description or "")
    assert "Celulares" in (r.description or "")
