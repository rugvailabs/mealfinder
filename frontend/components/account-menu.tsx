"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

export function AccountMenu() {
  const auth = useAuth();
  const router = useRouter();

  if (auth.status === "loading") return null;
  if (auth.status === "signed-out") {
    return (
      <Link href="/login" className="hover:underline">
        Sign in
      </Link>
    );
  }
  return (
    <span className="flex items-center gap-3">
      <span className="opacity-70" data-testid="signed-in-phone">
        {auth.user.phone}
      </span>
      <button
        type="button"
        className="hover:underline"
        onClick={async () => {
          await auth.signOut();
          router.push("/");
        }}
      >
        Sign out
      </button>
    </span>
  );
}
