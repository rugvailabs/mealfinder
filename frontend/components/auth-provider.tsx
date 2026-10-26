"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  onSessionChange,
  refreshSession,
  setSession,
  signOut,
  type Role,
  type TokenOut,
  type User,
} from "@/lib/auth/session";

type AuthState =
  | { status: "loading"; user: null }
  | { status: "signed-out"; user: null }
  | { status: "signed-in"; user: User };

type AuthContextValue = AuthState & {
  signIn: (tokens: TokenOut) => void;
  signOut: () => Promise<void>;
  hasRole: (role: Role) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function stateFor(user: User | null): AuthState {
  return user ? { status: "signed-in", user } : { status: "signed-out", user: null };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });

  useEffect(() => {
    const unsubscribe = onSessionChange((user) => setState(stateFor(user)));
    // Restore the session from the refresh cookie, if there is one.
    void refreshSession();
    return unsubscribe;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      signIn: setSession,
      signOut,
      hasRole: (role) => state.user?.roles.includes(role) ?? false,
    }),
    [state],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}
