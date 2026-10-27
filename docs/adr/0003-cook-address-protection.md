# 0003: Cook home address protection

- Status: accepted (requirement confirmed); implemented in Phase 2, item 1
- Date: 2026-10-26, revised 2026-10-27

## Context

Cooks cook at home. Their home address is needed for pickup by delivery agents and for admin checks. It must never reach customers or partner shops, whether directly, through a join, or by accident in a response schema.

## Decision

1. The address lives only in the `cook_addresses` table (one row per cook, address lines, pincode and a PostGIS `geography(POINT, 4326)`), owned by `cooks` and mapped by `CookAddress` in `cooks/models.py`. No customer-visible table has a foreign key to it.
2. All reads and writes go through `app/modules/cooks/address.py`. That is the **only** file besides `cooks/models.py` allowed to name `cook_addresses` or `CookAddress`, and a test enforces this across `app/`.
3. `read_cook_address(db, actor, cook_id)` is the single way to read an address. It decides the purpose from the actor:
   - `cook_self`: the cook reading their own address
   - `admin`: any admin
   - `assigned_run`: an agent on an active run for this cook (added with logistics in Phase 4)

   Anyone else gets **404**, never 403, so a caller can't tell whether the cook or the address exists. `cooks/service.py` re-exports the function as the public API.
4. **Every call writes an `audit_log` row**: actor, cook, purpose, outcome (`allowed`, `denied`, `not_found`) and time. An allowed read is recorded in the same transaction as the read. A refusal is recorded on a separate connection, because the request's own transaction rolls back with the error.
5. Customer-facing and shop-facing queries never join `cook_addresses`. Their response schemas carry no address fields. Shops see only the cook's display name and the assigned shop. The admin cook list shows only whether an address is on file (`has_address`), not the address.

## Consequences

- Adding an address field to any other schema, or querying the table from anywhere else, fails CI.
- `tests/unit/test_address_leak.py` walks every response schema in the OpenAPI document, outside `/cooks/me*` and `/admin/*`, and fails on any field containing `address`, `street`, `pincode` or `geom`, or with a `lat`, `lng`, `latitude` or `longitude` name part.
- Audit volume grows with deliveries, so `audit_log` is append-only and indexed by `(subject_type, subject_id, created_at)`. It is shared with other audited actions (approvals, shop assignment) and keeps plain ids, not foreign keys, so the trail outlives the rows it mentions.
