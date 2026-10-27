import struct

import pytest
from geoalchemy2 import WKBElement

from app.core.geo import LatLng


def test_ewkt_puts_longitude_first() -> None:
    assert LatLng(lat=17.385, lng=78.4867).to_ewkt() == "SRID=4326;POINT(78.4867 17.385)"


@pytest.mark.parametrize("text", ["SRID=4326;POINT(78.4867 17.385)", "POINT(78.4867 17.385)"])
def test_reads_text(text: str) -> None:
    assert LatLng.from_db(text) == LatLng(lat=17.385, lng=78.4867)


@pytest.mark.parametrize("order", ["<", ">"])
def test_reads_wkb_and_ewkb(order: str) -> None:
    flag = 1 if order == "<" else 0
    plain = struct.pack(f"{order}BIdd", flag, 1, 78.4867, 17.385)
    extended = struct.pack(f"{order}BIIdd", flag, 0x20000001, 4326, 78.4867, 17.385)
    for data in (plain, extended):
        assert LatLng.from_db(WKBElement(data)) == LatLng(lat=17.385, lng=78.4867)


def test_rejects_non_points() -> None:
    with pytest.raises(ValueError):
        LatLng.from_db("LINESTRING(0 0, 1 1)")
    with pytest.raises(ValueError):
        LatLng.from_db(WKBElement(struct.pack("<BIdd", 1, 2, 0, 0)))
