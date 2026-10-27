"""Part 4, admin side: listing cooks and moving them through approval."""

from httpx import AsyncClient

from app.core.auth import Role
from tests.integration.conftest import SignIn
from tests.integration.cooks.helpers import ADMIN, add_address, apply, decide

COOK = "+919800000001"
OTHER_COOK = "+919800000002"
ADMIN_PHONE = "+919800000099"


async def test_only_admins_reach_the_admin_endpoints(client: AsyncClient, sign_in: SignIn) -> None:
    cook = await sign_in(COOK)
    cook_id = await apply(client, cook)
    assert (await client.get(f"{ADMIN}/cooks")).status_code == 401
    assert (await client.get(f"{ADMIN}/cooks", headers=cook)).status_code == 403
    response = await client.post(f"{ADMIN}/cooks/{cook_id}/approve", headers=cook)
    assert response.status_code == 403


async def test_list_shows_review_details_and_filters_by_status(
    client: AsyncClient, sign_in: SignIn
) -> None:
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    first = await sign_in(COOK)
    first_id = await apply(client, first, "First Kitchen")
    await add_address(client, first)
    second_id = await apply(client, await sign_in(OTHER_COOK), "Second Kitchen")

    listed = (await client.get(f"{ADMIN}/cooks", headers=admin)).json()
    assert [c["id"] for c in listed] == [first_id, second_id]  # oldest submission first
    assert listed[0]["phone"] == COOK
    assert listed[0]["has_address"] is True
    assert listed[1]["has_address"] is False
    assert not {"address", "line1", "pincode", "lat", "lng", "geom"} & set(listed[0])

    await decide(client, admin, second_id, "reject", "Incomplete details")
    rejected = await client.get(f"{ADMIN}/cooks", params={"status": "rejected"}, headers=admin)
    assert [c["id"] for c in rejected.json()] == [second_id]
    bad = await client.get(f"{ADMIN}/cooks", params={"status": "nope"}, headers=admin)
    assert bad.status_code == 422


async def test_approve_needs_an_address(client: AsyncClient, sign_in: SignIn) -> None:
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    cook = await sign_in(COOK)
    cook_id = await apply(client, cook)

    response = await client.post(f"{ADMIN}/cooks/{cook_id}/approve", headers=admin)
    assert response.status_code == 409
    assert response.json()["type"].endswith("/address_required")

    await add_address(client, cook)
    approved = await decide(client, admin, cook_id, "approve")
    assert approved["approval_status"] == "approved"
    assert approved["approved_at"] is not None
    me = (await client.get("/api/v1/auth/me", headers=admin)).json()
    assert approved["approved_by"] == me["id"]


async def test_full_lifecycle_and_refused_transitions(client: AsyncClient, sign_in: SignIn) -> None:
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    cook = await sign_in(COOK)
    cook_id = await apply(client, cook)
    await add_address(client, cook)

    async def refused(action: str, reason: str | None = None) -> None:
        body = {"reason": reason} if reason else None
        response = await client.post(f"{ADMIN}/cooks/{cook_id}/{action}", json=body, headers=admin)
        assert response.status_code == 409, (action, response.text)
        assert response.json()["type"].endswith("/invalid_transition")

    # pending: can't be suspended.
    await refused("suspend", "Too early")

    # approved: can't be approved or rejected again, can be suspended.
    await decide(client, admin, cook_id, "approve")
    await refused("approve")
    await refused("reject", "Changed my mind")
    suspended = await decide(client, admin, cook_id, "suspend", "Hygiene complaint")
    assert suspended["approval_status"] == "suspended"
    assert suspended["suspension_reason"] == "Hygiene complaint"

    # suspended: can't be rejected or suspended again; approve reinstates.
    await refused("reject", "Nope")
    await refused("suspend", "Again")
    assert (await decide(client, admin, cook_id, "approve"))["approval_status"] == "approved"

    own = (await client.get("/api/v1/cooks/me", headers=cook)).json()
    assert own["approval_status"] == "approved"


async def test_reject_and_suspend_need_a_reason(client: AsyncClient, sign_in: SignIn) -> None:
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    cook_id = await apply(client, await sign_in(COOK))
    for body in (None, {"reason": ""}, {"reason": "  "}):
        response = await client.post(f"{ADMIN}/cooks/{cook_id}/reject", json=body, headers=admin)
        assert response.status_code == 422, body


async def test_unknown_cook_is_404(client: AsyncClient, sign_in: SignIn) -> None:
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    response = await client.post(
        f"{ADMIN}/cooks/00000000-0000-0000-0000-000000000000/approve", headers=admin
    )
    assert response.status_code == 404
