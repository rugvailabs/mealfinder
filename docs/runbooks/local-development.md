# Local development

## Prerequisites

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Node 24
- Docker (for Postgres, or the whole stack)

## Backend

```sh
docker compose -f infra/docker-compose.yml up -d db
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload        # http://localhost:8000/api/v1/docs
```

Checks: `uv run ruff format . && uv run ruff check . && uv run mypy app && uv run pytest`

## Frontend

```sh
cd frontend
npm install
npm run dev                                  # http://localhost:3000
```

Checks: `npm run lint && npm run typecheck && npm run build && npm run e2e`

## Signing in locally

Local and test use the console SMS provider: the code is printed in the API log, and
`GET http://localhost:8000/api/v1/auth/_dev/last-otp?phone=%2B919876543210` returns it.
New numbers become customers. To give yourself another role (including the first admin):

```sh
cd backend
uv run python -m scripts.grant_role +919876543210 admin
```

## Running tests on Postgres

Tests use SQLite unless `MF_TEST_DATABASE_URL` is set (CI sets it). The suite drops and
recreates its tables, so point it at a separate database:

```sh
docker compose -f infra/docker-compose.yml exec db psql -U mealfinder -c "create database mealfinder_test"
MF_TEST_DATABASE_URL=postgresql+asyncpg://mealfinder:mealfinder@localhost:5432/mealfinder_test uv run pytest
```

## When you change the API

The frontend's typed client is generated from a committed OpenAPI snapshot, and CI fails if the snapshot is stale.

```sh
cd backend && uv run python -m scripts.export_openapi
cd ../frontend && npm run gen:api
```

## Adding a migration

```sh
cd backend
uv run alembic revision --autogenerate -m "orders: add order table"
```

Review the generated file before committing. There must only ever be one head (`uv run alembic heads`).
