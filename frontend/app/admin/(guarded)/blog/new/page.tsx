import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { AdminProductListItem, Paginated } from "@/lib/admin/types";
import BlogForm from "../BlogForm";

export const metadata = { title: "New post — Karivex Control Center" };

export default async function NewBlogPostPage() {
  const token = await getAdminToken();
  if (!token) return null;
  const products = await adminGet<Paginated<AdminProductListItem>>("/dashboard/products/?page_size=500", token);

  return (
    <>
      <h1>New blog post</h1>
      <BlogForm products={products.results} />
    </>
  );
}
