import type { components } from "@/lib/api/schema";

export type TokenOut = components["schemas"]["TokenOut"];
export type User = components["schemas"]["UserOut"];
export type Role = User["roles"][number];

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// The access token lives only in memory. The refresh token is an httpOnly cookie that
// JavaScript never sees; the API rotates it on every refresh.
let accessToken: string | null = null;
let inFlight: Promise<TokenOut | null> | null = null;
const listeners = new Set<(user: User | null) => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setSession(tokens: TokenOut | null): void {
  accessToken = tokens?.access_token ?? null;
  for (const listener of listeners) listener(tokens?.user ?? null);
}

export function onSessionChange(listener: (user: User | null) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function callRefresh(): Promise<TokenOut | null> {
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    return response.ok ? ((await response.json()) as TokenOut) : null;
  } catch {
    return null; // API unreachable: treat as signed out.
  }
}

/**
 * Exchange the refresh cookie for a new access token.
 *
 * Refresh tokens are single-use and reusing one ends the session, so refreshes must never
 * overlap: calls within a tab share one request, and tabs queue on a Web Lock so each one
 * sends the cookie the previous tab just received.
 */
export function refreshSession(): Promise<TokenOut | null> {
  inFlight ??= (async () => {
    const tokens =
      typeof navigator !== "undefined" && navigator.locks
        ? await navigator.locks.request("mf-auth-refresh", callRefresh)
        : await callRefresh();
    setSession(tokens);
    return tokens;
  })().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

export async function signOut(): Promise<void> {
  try {
    await fetch(`${API_URL}/api/v1/auth/logout`, { method: "POST", credentials: "include" });
  } finally {
    setSession(null);
  }
}

/** Only same-site relative paths, so `?next=` can't send people to another site. */
export function safeNextPath(next: string | null | undefined): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}
