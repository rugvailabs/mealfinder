# Meal Finder

A marketplace for home-cooked meals, with portals for customers, cooks, delivery agents, shops and admins.

```
backend/    FastAPI modular monolith: app/core (infra) + app/modules (bounded contexts), Alembic, pytest
frontend/   Next.js App Router: (customer) (cook) (agent) (shop) (admin), typed client in lib/api, Playwright in e2e/
infra/      docker-compose.yml, deploy manifests
docs/       adr/ (decisions), runbooks/
.github/    ci-backend, ci-frontend, e2e, deploy
```

## Quick start

```sh
docker compose -f infra/docker-compose.yml up --build
```

- Web: http://localhost:3000
- API docs: http://localhost:8000/api/v1/docs

For running each side on its own, see [docs/runbooks/local-development.md](docs/runbooks/local-development.md).

## Architecture

- [ADR 0001: Modular monolith](docs/adr/0001-modular-monolith.md)
- [ADR 0002: Transactional outbox](docs/adr/0002-transactional-outbox.md)
- [ADR 0003: Cook home address protection](docs/adr/0003-cook-address-protection.md)
- [ADR 0004: SMS OTP sign-in, sessions and roles](docs/adr/0004-authentication-and-sessions.md)
