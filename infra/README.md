# infra

- `docker-compose.yml` runs the full stack locally: Postgres, a one-shot `migrate`, `api`, the outbox `worker` and `web`.
  ```sh
  docker compose -f infra/docker-compose.yml up --build
  ```
  Host ports default to 5432 (db), 8000 (api) and 3000 (web). If one is taken, override it, for example `MF_DB_PORT=5433 docker compose -f infra/docker-compose.yml up`. `MF_API_PORT` and `MF_WEB_PORT` work the same way.
- `deploy/` holds environment manifests once a hosting target is chosen (see `docs/adr`).
