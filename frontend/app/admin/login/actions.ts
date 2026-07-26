"use server";
import { redirect } from "next/navigation";
import { setAdminSession } from "@/lib/admin/session";

const API = process.env.INTERNAL_API_URL ?? "http://karivex_backend:8000";

export type LoginState = { error: string | null };

export async function loginAction(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const username = String(formData.get("username") ?? "");
  const password = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/admin");

  let data: { token: string; expires_in: number };
  try {
    const res = await fetch(`${API}/api/dashboard/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      cache: "no-store",
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      return { error: body?.detail ?? "Invalid username or password." };
    }
    data = await res.json();
  } catch {
    return { error: "Could not reach the server. Please try again." };
  }

  await setAdminSession(data.token, data.expires_in);
  redirect(next.startsWith("/admin") ? next : "/admin"); // after try/catch, never inside it
}
