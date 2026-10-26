# frontend

Next.js App Router with one route group per portal:

| Group        | URL       | Who               |
| ------------ | --------- | ----------------- |
| `(customer)` | `/`       | Customers         |
| `(cook)`     | `/cook`   | Home cooks        |
| `(agent)`    | `/agent`  | Delivery agents   |
| `(shop)`     | `/shop`   | Partner shops     |
| `(admin)`    | `/admin`  | Operations        |

- `lib/api/`: `openapi.json` is exported from the backend; `npm run gen:api` turns it into `schema.d.ts`, used by the typed `api` client in `client.ts`.
- `e2e/`: Playwright (`npm run e2e`). It starts `npm run dev` itself unless `E2E_BASE_URL` points at a running app.

See [../docs/runbooks/local-development.md](../docs/runbooks/local-development.md).
