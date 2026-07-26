"use server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminMutate, AdminApiError, formatDrfError } from "@/lib/admin/api";

export type CategoryFormState = { error: string | null };

export async function createCategoryAction(_prev: CategoryFormState, formData: FormData): Promise<CategoryFormState> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  const body = {
    name: formData.get("name"),
    description: formData.get("description") ?? "",
    meta_title: formData.get("meta_title") ?? "",
    meta_description: formData.get("meta_description") ?? "",
  };
  try {
    await adminMutate("/dashboard/categories/", token, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
  revalidatePath("/admin/categories");
  return { error: null };
}

export async function updateCategoryAction(id: number, _prev: CategoryFormState, formData: FormData): Promise<CategoryFormState> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  const body = {
    name: formData.get("name"),
    description: formData.get("description") ?? "",
    meta_title: formData.get("meta_title") ?? "",
    meta_description: formData.get("meta_description") ?? "",
  };
  try {
    await adminMutate(`/dashboard/categories/${id}/`, token, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
  revalidatePath("/admin/categories");
  return { error: null };
}

export async function deleteCategoryAction(id: number) {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  await adminMutate(`/dashboard/categories/${id}/`, token, { method: "DELETE" });
  revalidatePath("/admin/categories");
}
