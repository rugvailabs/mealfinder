import createClient from "openapi-fetch";

import type { paths } from "./schema";

// Types in ./schema.d.ts are generated from the backend's OpenAPI document:
//   cd backend && uv run python -m scripts.export_openapi
//   cd frontend && npm run gen:api
export const api = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

export type { paths };
