import createClient from "openapi-fetch";

import { API_URL, getAccessToken, refreshSession } from "@/lib/auth/session";

import type { paths } from "./schema";

// Types in ./schema.d.ts are generated from the backend's OpenAPI document:
//   cd backend && uv run python -m scripts.export_openapi
//   cd frontend && npm run gen:api

// Endpoints that must not trigger a refresh-and-retry on 401.
const NO_RETRY = ["/api/v1/auth/otp/", "/api/v1/auth/refresh"];

function withToken(request: Request): Request {
  const token = getAccessToken();
  if (token) request.headers.set("Authorization", `Bearer ${token}`);
  return request;
}

/** Sends the access token, and on a 401 refreshes once and retries the request. */
async function authFetch(request: Request): Promise<Response> {
  const retry = request.clone();
  const response = await fetch(withToken(request));
  if (response.status !== 401 || NO_RETRY.some((path) => request.url.includes(path))) {
    return response;
  }
  return (await refreshSession()) ? fetch(withToken(retry)) : response;
}

export const api = createClient<paths>({
  baseUrl: API_URL,
  fetch: authFetch,
  credentials: "include", // the refresh cookie is set and cleared by auth responses
});

/** The `detail` of an RFC 9457 problem response, for showing to the user. */
export function problemDetail(error: unknown, fallback = "Something went wrong"): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return fallback;
}

export type { paths };
