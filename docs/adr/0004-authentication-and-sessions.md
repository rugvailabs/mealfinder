# 0004: SMS OTP sign-in, rotating refresh tokens and multi-role accounts

- Status: accepted
- Date: 2026-10-26

## Context

Everyone (customers, cooks, delivery agents, shops, admins) signs in with a mobile number. Sessions must be revocable on the server (logout, logout everywhere, suspension, a stolen device), and one person can hold several roles, such as a cook who also orders as a customer.

## Decision

**Sign-in is SMS OTP only, through MSG91, behind an adapter.**

- `app/core/sms.py` defines `SmsSender`. `Msg91SmsSender` calls MSG91's v5 OTP API with a code *we* generate, so verification stays local and switching provider means writing one class. `ConsoleSmsSender` logs codes for local and test, and settings refuse it everywhere else.
- Codes are 6 digits and valid for 5 minutes. They are stored as an HMAC bound to the phone number, compared in constant time, and single-use. A challenge locks after 5 wrong attempts. Each failed attempt is committed before the error is returned, so a rollback can't erase it.
- A number can ask for a new code every 30 seconds, and at most 5 times per hour (429 with `Retry-After`). Per-IP limits wait for Redis.
- Requesting a code behaves identically for new and existing numbers. A number's first successful verification creates the account with the `customer` role.

**Sessions use a short JWT, a rotating refresh token, and a server-side session row.**

- `sessions` has one row per signed-in device. The access token is a 15-minute JWT carrying `sub` (user), `sid` (session) and `roles`, and is held in memory by the frontend only.
- The refresh token is 256 random bits, stored as SHA-256 in `refresh_tokens`. It is sent as an `httpOnly`, `SameSite=Strict`, `Secure` (outside local) cookie, scoped to `/api/v1/auth`, and expires after 30 days.
- **Rotation:** each refresh atomically claims the token (`UPDATE ... WHERE used_at IS NULL`) and issues a new one in the same session. **Reuse detection:** presenting an already-used token revokes the whole session, on the assumption it was stolen.
- **Revocation is immediate.** Every authenticated request checks the session is live and the user active, and reads roles fresh from `user_roles`. Logout, logout-all, suspension and role changes all take effect on the next request, not when the JWT expires. The cost is one indexed lookup per request.
- The frontend serialises refreshes (single-flight within a tab, a Web Lock across tabs), so legitimate concurrent refreshes never look like reuse.

**Roles live in `user_roles`, one row per role.**

- Valid roles are `customer`, `cook`, `agent`, `shop` and `admin`, enforced by a check constraint. `identity.service.grant_role` and `revoke_role` are the only writers. The cooks module (on approval) and admin call them.
- Bootstrap the first admin with `uv run python -m scripts.grant_role +91XXXXXXXXXX admin`.

**Every module can protect routes without depending on identity.**

- `Role`, `Principal`, `CurrentPrincipal` and `require_roles(...)` live in `app/core/auth.py`. Identity registers the session check (`load_principal`) at startup in `app/main.py`. This keeps the dependency table in ADR 0001 intact: catalog, for example, can require `Role.COOK` while depending only on cooks.

## Consequences

- A stolen access token works for at most 15 minutes, and not at all once its session is revoked. A stolen refresh token works once, and the victim's next refresh then ends the session.
- Two browser processes with separate cookie jars refreshing at the same instant would trip reuse detection. That's acceptable, since the user simply signs in again.
- In local and test only, `GET /api/v1/auth/_dev/last-otp?phone=` returns the last console-provider code for e2e tests. It isn't mounted elsewhere, and a test asserts that.
- The MSG91 adapter is unverified against a live account. Before launch, confirm the DLT-registered template and its OTP variable with MSG91.
