import { notFound } from "next/navigation";
import { getAdminToken } from "@/lib/admin/session";
import { adminGet, AdminApiError } from "@/lib/admin/api";
import type { AdminBlogPost, AdminProductListItem, Paginated } from "@/lib/admin/types";
import BlogForm from "../../BlogForm";

export const metadata = { title: "Edit post — Karivex Control Center" };

export default async function EditBlogPostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await getAdminToken();
  if (!token) return null;

  let post: AdminBlogPost;
  try {
    post = await adminGet<AdminBlogPost>(`/dashboard/blog/${id}/`, token);
  } catch (e) {
    if (e instanceof AdminApiError && e.status === 404) notFound();
    throw e;
  }
  const products = await adminGet<Paginated<AdminProductListItem>>("/dashboard/products/?page_size=500", token);

  return (
    <>
      <h1>Edit post</h1>
      <BlogForm post={post} products={products.results} />
    </>
  );
}
