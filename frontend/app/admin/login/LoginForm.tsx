"use client";
import { useActionState } from "react";
import { loginAction, type LoginState } from "./actions";

const initialState: LoginState = { error: null };

export default function LoginForm({ next }: { next: string }) {
  const [state, formAction, pending] = useActionState(loginAction, initialState);

  return (
    <form action={formAction}>
      <input type="hidden" name="next" value={next} />
      <label>
        Username
        <input name="username" required autoFocus autoComplete="username" />
      </label>
      <label>
        Password
        <input name="password" type="password" required autoComplete="current-password" />
      </label>
      <button disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button>
      {state.error && <p className="admin-login-error" role="alert">{state.error}</p>}
    </form>
  );
}
