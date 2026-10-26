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
