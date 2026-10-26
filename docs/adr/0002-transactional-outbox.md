# 0002: Transactional outbox for cross-module side effects

- Status: accepted
- Date: 2026-10-26

## Context

Placing an order must reliably trigger notifications, cook alerts, payment capture and delivery dispatch. Calling those inline couples the request to slow or flaky providers, and firing them after commit loses events when the process dies in between.

## Decision

- Modules call `app.core.outbox.enqueue(session, topic, payload)` inside the same transaction as their state change.
- Subscribers register with `@subscribe("topic")`. The `outbox.dispatch` job (`python -m app.core.jobs outbox.dispatch`) delivers pending events, using `FOR UPDATE SKIP LOCKED` on Postgres so several workers can run at once.
- Delivery is **at least once**. A failed handler increments `attempts` and is retried, up to `MAX_ATTEMPTS`. Handlers must be idempotent.
- Topics are named `<module>.<event>` in the past tense, such as `orders.placed` or `payments.captured`.

## Consequences

- Side effects lag commits by up to the worker's poll interval (5 seconds in local compose).
- Events that keep failing stay in `outbox_events` with `last_error` set, for admins to inspect.
