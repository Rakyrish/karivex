"use server";
import { redirect } from "next/navigation";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminMutate, AdminApiError, formatDrfError } from "@/lib/admin/api";
import type { AIDraft, ProductFromUrl } from "@/lib/admin/types";

export type NewProductFacts = {
  name: string;
  category: string;
  grade: string;
  cas_number?: string;
  synonyms?: string;
  purity?: string;
  appearance?: string;
  packaging?: string;
  regions?: string;
  focus_keyword?: string;
  notes?: string;
  image_url?: string;
  source_url?: string;
};

export async function generateDraftAction(facts: NewProductFacts): Promise<{ draft?: AIDraft; error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  try {
    const draft = await adminMutate<AIDraft>("/dashboard/ai/new-product-draft/", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(facts),
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

/** AI-free lookup so the UI can show the photo the instant a URL is pasted,
 * before committing to the slow drafting call. Works for a direct image URL
 * and for a product page (whose og:image it pulls out). */
export async function resolveImageAction(
  url: string,
): Promise<{ image_url?: string; image_candidates?: string[]; is_image?: boolean; error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  try {
    return await adminMutate("/dashboard/ai/resolve-image/", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
}

/** Composes a reviewable product from ONE source: a URL (product page or
 * direct image), an uploaded photo, or just a name. `source` is a FormData
 * so the uploaded file streams straight through to Django. */
export async function composeProductAction(
  source: FormData,
): Promise<{ result?: ProductFromUrl; error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  try {
    const result = await adminMutate<ProductFromUrl>("/dashboard/ai/compose-product/", token, {
      method: "POST",
      body: source,
    });
    return { result };
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
}

export type CreateProductState = { error: string | null };

export async function createProductAction(_prev: CreateProductState, formData: FormData): Promise<CreateProductState> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  let created: { id: number } | null = null;
  try {
    created = await adminMutate<{ id: number }>("/dashboard/products/", token, {
      method: "POST",
      body: formData,
    });
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }

  redirect(`/admin/products/${created.id}/edit`); // after try/catch, never inside it
}
