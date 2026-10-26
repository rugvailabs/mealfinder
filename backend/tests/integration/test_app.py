from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import NotFoundError
from app.main import create_app


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"


async def test_openapi_is_served_under_api_prefix(client: AsyncClient) -> None:
    response = await client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Meal Finder API"


async def _problem_for(app: FastAPI, path: str) -> dict[str, object]:
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as c:
        response = await c.get(path, headers={"X-Request-ID": "req-1"})
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, object] = response.json()
    body["_status"] = response.status_code
    return body


async def test_app_errors_become_problem_json() -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("no such meal")

    body = await _problem_for(app, "/boom")
    assert body["_status"] == 404
    assert body["detail"] == "no such meal"
    assert body["request_id"] == "req-1"


async def test_unhandled_errors_hide_details() -> None:
    app = create_app()

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret internals")

    body = await _problem_for(app, "/crash")
    assert body["_status"] == 500
    assert "secret" not in str(body["detail"])
