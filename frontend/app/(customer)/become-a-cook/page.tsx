"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { api, problemDetail } from "@/lib/api/client";
import { refreshSession } from "@/lib/auth/session";
import { buttonClass, errorClass, inputClass } from "@/lib/ui/styles";

export default function BecomeACookPage() {
  const auth = useAuth();
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isCook = auth.hasRole("cook");
  useEffect(() => {
    if (auth.status === "signed-out") router.replace("/login?next=%2Fbecome-a-cook");
    else if (isCook) router.replace("/cook/profile");
  }, [auth.status, isCook, router]);

  if (auth.status !== "signed-in" || isCook) {
    return <p className="opacity-60">Loading…</p>;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await api.POST("/api/v1/cooks/me", {
      body: { display_name: displayName, bio: bio || null },
    });
    if (error) {
      setBusy(false);
      return setError(problemDetail(error, "Could not send your application"));
    }
    // Applying grants the cook role; pick it up before entering the cook portal.
    await refreshSession();
    router.push("/cook/profile");
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Cook with us</h1>
        <p className="opacity-70">
          Tell customers who you are. After you apply, add your home address so our team can review
          your application. Your address is never shown to customers or shops.
        </p>
      </div>
      <form className="space-y-4" onSubmit={submit}>
        <label className="block space-y-1">
          <span className="text-sm">Kitchen name</span>
          <input
            className={inputClass}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            minLength={2}
            maxLength={80}
            required
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm">About your cooking (optional)</span>
          <textarea
            className={inputClass}
            rows={4}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            maxLength={1000}
          />
        </label>
        <button className={buttonClass} disabled={busy}>
          Apply
        </button>
      </form>
      {error && (
        <p role="alert" className={errorClass}>
          {error}
        </p>
      )}
    </div>
  );
}
