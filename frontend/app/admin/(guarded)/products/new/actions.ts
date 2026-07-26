"use server";
import { redirect } from "next/navigation";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminMutate, AdminApiError, formatDrfError } from "@/lib/admin/api";
import type { AIDraft } from "@/lib/admin/types";

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
