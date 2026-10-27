"""ADR 0003: no response outside the cook-self and admin APIs carries an address-like field.

Checks the OpenAPI document, which is exactly what clients see: every response schema of
every operation, following $refs into nested objects, arrays and unions.
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.main import create_app

# Substrings that mark an address-like field name.
FORBIDDEN = ("address", "street", "pincode", "geom")
# Whole name parts (split on "_"), so "lat" catches "lat" and "pickup_lat" but not "translated".
FORBIDDEN_PARTS = {"lat", "lng", "latitude", "longitude"}

# The only APIs allowed to return address fields: the cook's own, and admin.
ALLOWED_PREFIXES = ("/api/v1/cooks/me", "/api/v1/admin/")


def _is_forbidden(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in FORBIDDEN) or bool(
        FORBIDDEN_PARTS & set(lowered.split("_"))
    )


def _schema_fields(
    schema: dict[str, Any], components: dict[str, Any], path: str, seen: set[str]
) -> list[str]:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            return []
        return _schema_fields(components[name], components, name, seen | {name})
    found: list[str] = []
    for prop, sub in schema.get("properties", {}).items():
        here = f"{path}.{prop}"
        if _is_forbidden(prop):
            found.append(here)
        found += _schema_fields(sub, components, here, seen)
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            found += _schema_fields(schema[key], components, path, seen)
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(key, []):
            found += _schema_fields(sub, components, path, seen)
    return found


def leaks(app: FastAPI) -> dict[str, list[str]]:
    """Address-like response fields per operation, outside the allowed APIs."""
    spec = app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    result: dict[str, list[str]] = {}
    for path, operations in spec["paths"].items():
        if path.startswith(ALLOWED_PREFIXES):
            continue
        for method, operation in operations.items():
            for status, response in operation.get("responses", {}).items():
                for media in response.get("content", {}).values():
                    fields = _schema_fields(media.get("schema", {}), components, "", set())
                    if fields:
                        result[f"{method.upper()} {path} {status}"] = fields
    return result


def test_no_public_response_has_address_fields() -> None:
    assert leaks(create_app()) == {}


def test_the_allowlist_covers_only_cook_self_and_admin() -> None:
    paths = create_app().openapi()["paths"]
    exempt = sorted(p for p in paths if p.startswith(ALLOWED_PREFIXES))
    assert "/api/v1/cooks/me/address" in exempt
    assert "/api/v1/admin/cooks" in exempt
    # Other cook routes (a future public cook page, say) are checked.
    assert not any(
        p.startswith("/api/v1/cooks/") and not p.startswith("/api/v1/cooks/me") for p in exempt
    )


def test_the_check_catches_a_leak() -> None:
    from app.modules.cooks.schemas import HomeAddressOut

    class Leaky(BaseModel):
        cooks: list[HomeAddressOut] | None = None

    class Sneaky(BaseModel):
        pickup_lat: float
        street_name: str
        shop_geom: str
        translated: str

    app = FastAPI()

    @app.get("/api/v1/catalog/cooks")
    def leaky() -> Leaky:
        raise NotImplementedError

    @app.get("/api/v1/shops/{id}")
    def sneaky() -> Sneaky:
        raise NotImplementedError

    @app.get("/api/v1/cooks/me/address")
    def allowed() -> HomeAddressOut:
        raise NotImplementedError

    assert leaks(app) == {
        "GET /api/v1/catalog/cooks 200": [
            "HomeAddressOut.pincode",
            "HomeAddressOut.lat",
            "HomeAddressOut.lng",
        ],
        "GET /api/v1/shops/{id} 200": [
            "Sneaky.pickup_lat",
            "Sneaky.street_name",
            "Sneaky.shop_geom",
        ],
    }
