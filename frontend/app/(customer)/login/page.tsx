import { Suspense } from "react";

import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    // LoginForm reads ?next=, so it renders on the client inside this boundary.
    <Suspense fallback={<p className="opacity-60">Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}
