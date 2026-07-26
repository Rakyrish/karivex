"use server";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminMutate, AdminApiError, formatDrfError } from "@/lib/admin/api";

export type BlogFormState = { error: string | null };

export async function createBlogAction(_prev: BlogFormState, formData: FormData): Promise<BlogFormState> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  let created: { id: number } | null = null;
  try {
    created = await adminMutate<{ id: number }>("/dashboard/blog/", token, { method: "POST", body: formData });
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
  redirect(`/admin/blog/${created.id}/edit`);
}

export async function updateBlogAction(id: number, _prev: BlogFormState, formData: FormData): Promise<BlogFormState> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  try {
    await adminMutate(`/dashboard/blog/${id}/`, token, { method: "PATCH", body: formData });
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: formatDrfError(e.body) };
    }
    throw e;
  }
  revalidatePath(`/admin/blog/${id}/edit`);
  return { error: null };
}

export async function deleteBlogAction(id: number) {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  await adminMutate(`/dashboard/blog/${id}/`, token, { method: "DELETE" });
  redirect("/admin/blog");
}
