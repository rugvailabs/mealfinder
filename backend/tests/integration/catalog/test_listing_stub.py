"""Part 6: the approved-cook dependency guards listing endpoints.

The stub answers 501 only after the dependency lets the caller through, so a 403 here can
only come from the dependency, and an approved cook reaching 501 proves it passed.
"""

from fastapi import FastAPI
from httpx import AsyncClient

from app.core.auth import Role
from app.core.errors import AppError
from app.modules.cooks import service as cooks
from tests.integration.conftest import SignIn
from tests.integration.cooks.helpers import add_address, apply, decide

LISTINGS = "/api/v1/catalog/listings"
ADMIN_PHONE = "+919800000099"


async def _status(client: AsyncClient, headers: dict[str, str]) -> tuple[int, str]:
    response = await client.post(LISTINGS, headers=headers)
    return response.status_code, response.json()["type"].rsplit("/", 1)[-1]


async def test_listing_requires_an_approved_cook(client: AsyncClient, sign_in: SignIn) -> None:
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    assert (await client.post(LISTINGS)).status_code == 401

    # A customer who never applied, and an admin, are not approved cooks.
    assert await _status(client, await sign_in("+919800000003")) == (403, "cook_not_approved")
    assert await _status(client, admin) == (403, "cook_not_approved")

    cook = await sign_in("+919800000001")
    cook_id = await apply(client, cook)
    assert await _status(client, cook) == (403, "cook_not_approved")  # pending

    await decide(client, admin, cook_id, "reject", "Missing details")
    assert await _status(client, cook) == (403, "cook_not_approved")  # rejected

    await client.post("/api/v1/cooks/me/resubmit", headers=cook)
    await add_address(client, cook)
    await decide(client, admin, cook_id, "approve")
    assert await _status(client, cook) == (501, "not_implemented")  # through to the stub

    await decide(client, admin, cook_id, "suspend", "Complaint under review")
    assert await _status(client, cook) == (403, "cook_not_approved")  # suspended

    await decide(client, admin, cook_id, "approve")
    assert await _status(client, cook) == (501, "not_implemented")  # reinstated


async def test_listing_route_runs_the_approved_cook_dependency(
    app: FastAPI, client: AsyncClient
) -> None:
    # Swap the dependency for one that always refuses: if the route used anything else,
    # it would still answer 401/501 instead of this.
    class Sentinel(AppError):
        status_code = 418
        code = "sentinel"

    async def refuse() -> None:
        raise Sentinel("dependency ran")

    app.dependency_overrides[cooks.require_approved_cook.dependency] = refuse
    response = await client.post(LISTINGS)
    assert response.status_code == 418
    assert response.json()["detail"] == "dependency ran"
