# 0003: Cook home address protection

- Status: accepted (requirement confirmed)
- Date: 2026-10-26

## Context

Cooks cook at home. Their home address is needed for pickup by delivery agents and for admin checks. It must never reach customers or partner shops, whether directly, through a join, or by accident in a response schema.

## Decision

1. The address lives only in the `cook_addresses` table, owned by `cooks`, and is mapped by `CookAddress` in `cooks/models.py`.
2. All reads and writes go through `app/modules/cooks/address.py`. That is the **only** file besides `cooks/models.py` allowed to name `cook_addresses` or `CookAddress`, and a test enforces this across `app/`.
3. `address.py` exposes narrow functions that take the acting user and a purpose, for example:
   - `get_for_assigned_run(actor, cook_id, run_id)` for logistics, which checks that the agent is assigned to an active run for this cook
   - `get_for_admin(actor, cook_id, reason)` for admin
   Each one writes an audit row (who, which cook, purpose, when) in the same transaction as the read. `cooks/service.py` re-exports them as the public API.
4. Customer-facing and shop-facing queries never join `cook_addresses`. Their response schemas carry no address fields. Shops see only the cook's display name and the assigned shop.
5. Only `logistics` (for assigned runs) and `admin` may call the address functions. `cooks` itself serves the cook's own address to the cook.

## Consequences

- Adding an address field to any other schema, or querying the table from anywhere else, fails CI.
- Audit volume grows with deliveries, so the audit table is append-only and indexed by `(cook_id, created_at)`.
- When the cooks module is built, it adds a test asserting that every customer and shop response schema has no field matching `address|street|lat|lng|geo`.
