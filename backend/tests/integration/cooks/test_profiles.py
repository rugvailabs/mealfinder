"""Part 1 and the cook-self endpoints of part 4: applying, editing and resubmitting."""

from httpx import AsyncClient

from app.core.auth import Role
from tests.integration.conftest import SignIn
from tests.integration.cooks.helpers import ADMIN, COOKS, add_address, apply, decide

COOK = "+919800000001"
ADMIN_PHONE = "+919800000099"


async def test_applying_creates_a_pending_profile_and_grants_the_cook_role(
    client: AsyncClient, sign_in: SignIn
) -> None:
    headers = await sign_in(COOK)

    # A customer has no cook profile and no access to the cook-self endpoints yet.
    assert (await client.get(f"{COOKS}/me", headers=headers)).status_code == 403

    response = await client.post(
        f"{COOKS}/me", json={"display_name": "  Amma's Kitchen ", "bio": "Andhra"}, headers=headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["display_name"] == "Amma's Kitchen"
    assert body["approval_status"] == "pending"
    assert body["approved_at"] is None

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert sorted(me.json()["roles"]) == ["cook", "customer"]
    assert (await client.get(f"{COOKS}/me", headers=headers)).json()["id"] == body["id"]


async def test_applying_twice_conflicts(client: AsyncClient, sign_in: SignIn) -> None:
    headers = await sign_in(COOK)
    await apply(client, headers)
    response = await client.post(f"{COOKS}/me", json={"display_name": "Again"}, headers=headers)
    assert response.status_code == 409
    assert response.json()["type"].endswith("/cook_profile_exists")


async def test_profile_validation(client: AsyncClient, sign_in: SignIn) -> None:
    headers = await sign_in(COOK)
    response = await client.post(f"{COOKS}/me", json={"display_name": "A"}, headers=headers)
    assert response.status_code == 422


async def test_editing_never_changes_status(client: AsyncClient, sign_in: SignIn) -> None:
    cook = await sign_in(COOK)
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    cook_id = await apply(client, cook)

    for expected in ("pending", "rejected"):
        if expected == "rejected":
            await decide(client, admin, cook_id, "reject", "Photos of kitchen needed")
        response = await client.patch(
            f"{COOKS}/me", json={"display_name": "New Name", "bio": None}, headers=cook
        )
        assert response.status_code == 200, response.text
        assert response.json()["approval_status"] == expected
        assert response.json()["display_name"] == "New Name"
        assert response.json()["bio"] is None


async def test_resubmit_is_only_allowed_from_rejected_and_keeps_the_reason(
    client: AsyncClient, sign_in: SignIn
) -> None:
    cook = await sign_in(COOK)
    admin = await sign_in(ADMIN_PHONE, Role.ADMIN)
    cook_id = await apply(client, cook)

    pending = await client.post(f"{COOKS}/me/resubmit", headers=cook)
    assert pending.status_code == 409
    assert pending.json()["type"].endswith("/invalid_transition")

    await decide(client, admin, cook_id, "reject", "Kitchen photos needed")
    response = await client.post(f"{COOKS}/me/resubmit", headers=cook)
    assert response.status_code == 200, response.text
    assert response.json()["approval_status"] == "pending"
    assert response.json()["rejection_reason"] == "Kitchen photos needed"

    # The admin still sees why the cook was rejected last time.
    listed = await client.get(f"{ADMIN}/cooks", params={"status": "pending"}, headers=admin)
    assert listed.json()[0]["rejection_reason"] == "Kitchen photos needed"
    assert listed.json()[0]["rejected_at"] is not None

    # And it can't be resubmitted again while pending, nor once approved.
    assert (await client.post(f"{COOKS}/me/resubmit", headers=cook)).status_code == 409
    await add_address(client, cook)
    await decide(client, admin, cook_id, "approve")
    assert (await client.post(f"{COOKS}/me/resubmit", headers=cook)).status_code == 409
