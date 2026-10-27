"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth-provider";
import type { Role } from "@/lib/auth/session";

/**
 * Shows `children` only to signed-in users holding `role`. This is for UX only: the API
 * enforces the same roles on every request.
 */
export function RoleGate({ role, children }: { role: Role; children: ReactNode }) {
  const auth = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "signed-out") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [auth.status, pathname, router]);

  if (auth.status !== "signed-in") {
    return <p className="opacity-60">Loading…</p>;
  }
  if (!auth.hasRole(role)) {
    return (
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold">You don&apos;t have access to this page</h1>
        {role === "cook" ? (
          <p className="opacity-70">
            This area is for cooks.{" "}
            <Link href="/become-a-cook" className="underline">
              Apply to cook with us
            </Link>
          </p>
        ) : (
          <p className="opacity-70">
            This area is for {role} accounts. If you&apos;ve applied, we&apos;ll let you know once
            you&apos;re approved.
          </p>
        )}
      </section>
    );
  }
  return <>{children}</>;
}
