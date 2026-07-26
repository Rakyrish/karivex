import "server-only";

const API = process.env.INTERNAL_API_URL ?? "http://karivex_backend:8000";

export class AdminApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`Admin API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API}/api${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new AdminApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

/** Reads, always fresh — distinct from the public lib/api.ts's force-cache. */
export async function adminGet<T>(path: string, token: string): Promise<T> {
  return request<T>(path, token);
}

/** Writes — POST/PATCH/DELETE, JSON or FormData bodies. Never calls
 * redirect()/cookie APIs itself; callers decide that after inspecting the
 * thrown AdminApiError, always outside their own try/catch. */
export async function adminMutate<T>(path: string, token: string, init: RequestInit): Promise<T> {
  return request<T>(path, token, init);
}

/** Turns a DRF error body ({field: [msg,...]} or {detail: msg}) into one
 * human-readable line for inline form error display. */
export function formatDrfError(body: unknown): string {
  if (!body || typeof body !== "object") return "Something went wrong. Please try again.";
  const obj = body as Record<string, unknown>;
  if (typeof obj.detail === "string") return obj.detail;
  const parts: string[] = [];
  for (const [field, value] of Object.entries(obj)) {
    const msg = Array.isArray(value) ? value.join(" ") : String(value);
    parts.push(field === "non_field_errors" ? msg : `${field}: ${msg}`);
  }
  return parts.join(" ") || "Something went wrong. Please try again.";
}
