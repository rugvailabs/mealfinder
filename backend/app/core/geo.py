"""PostGIS points that also work on the SQLite test fallback.

On Postgres a `GeoPoint` column is `geography(POINT, 4326)`, so distance queries are in metres.
On SQLite it is plain text holding the same EWKT, which is enough for storing and reading back.
"""

import struct
from dataclasses import dataclass

from geoalchemy2 import Geography, WKBElement
from sqlalchemy import Text
from sqlalchemy.types import TypeEngine

SRID = 4326


def geo_point_type() -> TypeEngine[object]:
    # Spatial indexes are declared explicitly on each table so migrations stay reviewable.
    return Geography(geometry_type="POINT", srid=SRID, spatial_index=False).with_variant(
        Text(), "sqlite"
    )


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float

    def to_ewkt(self) -> str:
        # WKT puts longitude first.
        return f"SRID={SRID};POINT({self.lng} {self.lat})"

    @classmethod
    def from_db(cls, value: object) -> "LatLng":
        """Read a value loaded from a `geo_point_type()` column on either backend."""
        if isinstance(value, WKBElement):
            return cls._from_wkb(bytes(value.data))
        if isinstance(value, str):
            body = value.split(";", 1)[-1].strip()
            if body.upper().startswith("POINT(") and body.endswith(")"):
                lng, lat = (float(part) for part in body[6:-1].split())
                return cls(lat=lat, lng=lng)
        raise ValueError(f"not a point: {value!r}")

    @classmethod
    def _from_wkb(cls, data: bytes) -> "LatLng":
        order = "<" if data[0] == 1 else ">"
        (geom_type,) = struct.unpack_from(f"{order}I", data, 1)
        offset = 5 + (4 if geom_type & 0x20000000 else 0)  # EWKB carries the SRID inline
        if geom_type & 0xFF != 1:
            raise ValueError("not a point")
        lng, lat = struct.unpack_from(f"{order}dd", data, offset)
        return cls(lat=lat, lng=lng)
