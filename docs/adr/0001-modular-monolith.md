# 0001: Modular monolith with one database

- Status: accepted
- Date: 2026-10-26

## Context

Meal Finder has nine bounded contexts and a small team. No confirmed requirement justifies microservices: they would add network failure modes, deploy overhead and distributed transactions before we know where the real seams are.

## Decision

One FastAPI process and one Postgres database (with PostGIS), split into nine modules under `backend/app/modules/`. A separate worker process drains the outbox table for jobs and notifications.

```
Next.js (5 role layouts) ──> /api/v1 ──> modules ──> Postgres
                                            │
                                            └─ outbox_events ──> worker ──> notifications, jobs
```

| Module          | Owns                                                                   | May depend on                   |
| --------------- | ---------------------------------------------------------------------- | ------------------------------- |
| `identity`      | users, roles, sessions, OTP                                            | none                            |
| `cooks`         | profiles, approval, protected address, cook-to-shop assignment         | identity                        |
| `catalog`       | meals, listings, cap of five active listings per cook                  | cooks                           |
| `inventory`     | stock per listing per slot, reservations                               | catalog                         |
| `orders`        | booking lifecycle, state machine, cancellation                         | inventory, catalog, identity    |
| `payments`      | provider adapter, webhooks, refunds, ledger, commission                | orders                          |
| `logistics`     | partner shops (PostGIS), agents, handover scans, custody chain         | cooks, orders                   |
| `notifications` | templates and delivery                                                 | none (reads outbox events only) |
| `admin`         | approvals, settlements, audit views                                    | all, through their services     |

Rules, enforced by `backend/tests/unit/test_module_boundaries.py`:

- A module may import another only if the table above allows it, and only that module's public `service` or `schemas`. Never its `models`, `router` or internals.
- Rows in another module are referenced **by id only**: no cross-module ORM relationships and no joins across module tables. A database foreign key to another module's table is fine, and may even point against the import direction, because it creates no code dependency. For example, `cook_shop_assignments` (cooks) references `partner_shops` (logistics).
- Reacting to something that happened in another module is done through outbox events (ADR 0002). This is also how a module reaches "upstream" without breaking the dependency direction (for example, `payments` telling `orders` that a capture succeeded).
- `app/core` never imports from `app/modules`.
- Alembic keeps a **single linear head**, and CI fails if there are two.

Planned but not wired yet: object storage for meal photos (with catalog), and Redis for rate limits and caching (when load calls for it).

## Consequences

- A module can later be extracted into its own service by swapping its service calls for HTTP and its outbox topics for a broker.
- Cross-module reporting belongs in `admin`, built from service calls or read-only projections.
