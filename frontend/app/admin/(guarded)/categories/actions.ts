"use server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminMutate, AdminApiError, formatDrfError } from "@/lib/admin/api";

export type CategoryFormState = { error: string | null };

/** Build the outgoing body from the submitted form.
 *
 * Sent as multipart rather than JSON because the tile image is a file upload;
 * DRF parses both identically. Empty optional fields are omitted so a blank
 * input never overwrites an existing value with "" — notably `image`, which
 * arrives as a zero-byte File when the user didn't pick one, and `parent`,
 * where "" must become a real null to promote a category to a top-level
 * industry.
 */
function buildCategoryForm(formData: FormData): FormData {
  const out = new FormData();
  out.set("name", String(formData.get("name") ?? ""));
  out.set("description", String(formData.get("description") ?? ""));
  out.set("meta_title", String(formData.get("meta_title") ?? ""));
  out.set("meta_description", String(formData.get("meta_description") ?? ""));
  out.set("image_alt", String(formData.get("image_alt") ?? ""));

  const displayOrder = String(formData.get("display_order") ?? "").trim();
  if (displayOrder) out.set("display_order", displayOrder);

  // "" => top-level industry (null parent); a value => nest under that id.
  const parent = String(formData.get("parent") ?? "").trim();
  out.set("parent", parent);

  const image = formData.get("image");
  if (image instanceof File && image.size > 0) out.set("image", image);

  return out;
}

export async function createCategoryAction(_prev: CategoryFormState, formData: FormData): Promise<CategoryFormState> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  try {
    await adminMutate("/dashboard/categories/", token, {
      method: "POST", body: buildCategoryForm(formData),
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

  try {
    await adminMutate(`/dashboard/categories/${id}/`, token, {
      method: "PATCH", body: buildCategoryForm(formData),
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
