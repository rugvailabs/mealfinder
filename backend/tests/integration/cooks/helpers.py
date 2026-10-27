from typing import Any

from httpx import AsyncClient

COOKS = "/api/v1/cooks"
ADMIN = "/api/v1/admin"

ADDRESS: dict[str, Any] = {
    "line1": "12 Temple Street",
    "line2": "Near the water tank",
    "city": "Hyderabad",
    "pincode": "500001",
    "lat": 17.385,
    "lng": 78.4867,
}


async def apply(client: AsyncClient, headers: dict[str, str], name: str = "Amma's Kitchen") -> str:
    response = await client.post(
        f"{COOKS}/me", json={"display_name": name, "bio": "Andhra meals"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def add_address(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.put(f"{COOKS}/me/address", json=ADDRESS, headers=headers)
    assert response.status_code == 204, response.text


async def decide(
    client: AsyncClient, admin: dict[str, str], cook_id: str, action: str, reason: str | None = None
) -> dict[str, Any]:
    body = {"reason": reason} if reason is not None else None
    response = await client.post(f"{ADMIN}/cooks/{cook_id}/{action}", json=body, headers=admin)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result
