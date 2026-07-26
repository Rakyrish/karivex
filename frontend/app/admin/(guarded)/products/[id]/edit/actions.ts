"use server";
import { redirect } from "next/navigation";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminMutate, AdminApiError, formatDrfError } from "@/lib/admin/api";
import type { AIDraft } from "@/lib/admin/types";

export type EditState = { error: string | null; success?: boolean };

export async function updateProductAction(id: number, _prev: EditState, formData: FormData): Promise<EditState> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  try {
    await adminMutate(`/dashboard/products/${id}/`, token, { method: "PATCH", body: formData });
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
  return { error: null, success: true };
}

export async function regenerateDraftAction(
  id: number, notes: string, sourceUrl?: string
): Promise<{ draft?: AIDraft; error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  try {
    // Reuses the existing, unmodified ai_tools endpoint — works here because
    // this product already has a pk (unlike the new-product wizard's flow).
    const draft = await adminMutate<AIDraft>("/ai/draft-product/", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: id, notes, source_url: sourceUrl || undefined }),
    });
    return { draft };
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
}

export async function deleteProductAction(id: number) {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  await adminMutate(`/dashboard/products/${id}/`, token, { method: "DELETE" });
  redirect("/admin/products");
}
