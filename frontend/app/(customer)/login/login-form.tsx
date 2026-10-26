"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { api, problemDetail } from "@/lib/api/client";
import { safeNextPath, type User } from "@/lib/auth/session";

const HOME_BY_ROLE: [User["roles"][number], string][] = [
  ["admin", "/admin"],
  ["cook", "/cook"],
  ["agent", "/agent"],
  ["shop", "/shop"],
];

function homeFor(user: User): string {
  return HOME_BY_ROLE.find(([role]) => user.roles.includes(role))?.[1] ?? "/";
}

const inputClass =
  "w-full rounded border border-black/20 bg-transparent px-3 py-2 dark:border-white/25";
const buttonClass =
  "rounded bg-foreground px-4 py-2 font-medium text-background disabled:opacity-50";

export function LoginForm() {
  const auth = useAuth();
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));

  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("+91");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendIn, setResendIn] = useState(0);

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  async function sendCode() {
    setBusy(true);
    setError(null);
    const { data, error } = await api.POST("/api/v1/auth/otp/request", { body: { phone } });
    setBusy(false);
    if (error) return setError(problemDetail(error, "Could not send the code"));
    setStep("code");
    setResendIn(data.resend_after);
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error } = await api.POST("/api/v1/auth/otp/verify", { body: { phone, code } });
    setBusy(false);
    if (error) return setError(problemDetail(error, "That code didn't work"));
    auth.signIn(data);
    router.replace(next ?? homeFor(data.user));
  }

  return (
    <div className="mx-auto max-w-sm space-y-6">
      <h1 className="text-2xl font-semibold">Sign in</h1>

      {step === "phone" ? (
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void sendCode();
          }}
        >
          <label className="block space-y-1">
            <span className="text-sm">Mobile number</span>
            <input
              className={inputClass}
              type="tel"
              autoComplete="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
          </label>
          <button className={buttonClass} disabled={busy}>
            Send code
          </button>
        </form>
      ) : (
        <form className="space-y-3" onSubmit={verify}>
          <p className="text-sm opacity-70">We sent a code to {phone}.</p>
          <label className="block space-y-1">
            <span className="text-sm">Code</span>
            <input
              className={inputClass}
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              required
            />
          </label>
          <div className="flex items-center gap-4">
            <button className={buttonClass} disabled={busy || code.length < 4}>
              Verify
            </button>
            <button
              type="button"
              className="text-sm hover:underline disabled:opacity-50"
              disabled={busy || resendIn > 0}
              onClick={() => void sendCode()}
            >
              {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
            </button>
            <button
              type="button"
              className="text-sm hover:underline"
              onClick={() => {
                setStep("phone");
                setCode("");
              }}
            >
              Change number
            </button>
          </div>
        </form>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
