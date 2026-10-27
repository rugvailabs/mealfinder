# Roadmap

The phase plan for Meal Finder. Work proceeds in this order; when a phase or item finishes, the next one is the next line here. Change this file by PR when the plan changes.

## How each item ships

- Branch per item or phase from `main` (for example `phase-2-cooks`), PR into `main`. Never push to `main` directly.
- State the scope before implementing; report test results per scope item in the PR.
- Postgres-backed CI (`ci-backend`, `ci-frontend`) is the merge gate; run e2e locally before opening the PR.
- Stop for review at the end of each item when the item says so.

## Phase 0: Foundation — done

Modular monolith skeleton (nine modules, boundary test), Postgres + PostGIS, transactional outbox and job worker, Docker Compose, CI, ADRs 0001–0003.

## Phase 1: Identity — done

MSG91 SMS OTP behind an adapter, JWT access token plus rotating refresh cookie with server-side revocation, multi-role accounts via `user_roles`, role-gated portals for customer, cook, agent, shop and admin (ADR 0004).

## Phase 2: Catalog and shops

- Cooks: profile, protected address, shop assignment.
- Partner shops with PostGIS.
- Meals and listings, max 5 active per cook.
- Collection slots.
- Photo upload.
- Public shop and meal endpoints.
- Address-leak schema test.
- Cook editor and customer browse screens.

### Item 1: cooks module (branch `phase-2-cooks`, stop for review after)

1. `cook_profiles`: `display_name`, `bio`, `approval_status` (pending / approved / suspended / rejected), `approved_by`, `approved_at`. If approval already lives in identity from Phase 1, move it here and leave a compatibility import.
2. `cook_addresses`: one row per cook, address lines, PostGIS point. No FK from any customer-visible table. `read_cook_address(actor, cook_id)` writes an `audit_log` row on every call and is the only way to read it.
3. `cook_shop_assignments`: `cook_id`, `shop_id`, `active`. A minimal `partner_shops` table (`id`, `name`, `status`, `geom`) so the FK exists; the full shop module comes in item 2.
4. Endpoints: cook creates/updates own profile and address; admin lists, approves, rejects, suspends. A schema test asserts no response model outside the cook-self and admin schemas has fields named `address`, `street`, `pincode` or `geom`.
5. Frontend: cook profile and address form; admin cook list with approve / reject / suspend.
6. Tests: an unapproved cook gets 403 on any listing endpoint stub; an address read by the customer role returns 404; every address read produces an audit row.

### Item 2: partner shops

Full shop module on the item 1 `partner_shops` table. Detailed scope to be written when item 1 is reviewed.

## Phase 3: Booking and payments

- Inventory with a CHECK constraint and `SELECT … FOR UPDATE`.
- Orders state machine.
- Idempotency keys.
- 10-minute unpaid expiry via the job queue.
- Razorpay sandbox adapter.
- Webhooks deduplicated on event id.
- Refunds.
- Ledger entries.
- Cart, checkout and order screens.

## Phase 4: Logistics and notifications

- Agents and runs.
- Handover scans driving order transitions.
- Agent-only, audited address access.
- Notification templates on each transition.
- Redis for rate limits and cache.
- Agent, shop and cook screens.

## Phase 5: Pilot readiness

- Weekly settlements.
- Admin dashboards.
- Error tracking and tracing.
- Four paging alerts.
- Staging and production deploy workflow.
- Managed Postgres with WAL archiving, plus a restore drill.
- k6 load test.
- Security checklist.
- Runbooks.

## Phase 6: Pilot

- Seed shops and slots.
- Onboard cooks.
- Soft launch.
- Weekly KPI review.
