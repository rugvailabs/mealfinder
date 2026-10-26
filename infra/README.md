# infra

- `docker-compose.yml` runs the full stack locally: Postgres, a one-shot `migrate`, `api`, the outbox `worker` and `web`.
  ```sh
  docker compose -f infra/docker-compose.yml up --build
  ```
- `deploy/` holds environment manifests once a hosting target is chosen (see `docs/adr`).
