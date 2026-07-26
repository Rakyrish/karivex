import { notFound } from "next/navigation";
import { getAdminToken } from "@/lib/admin/session";
import { adminGet, AdminApiError } from "@/lib/admin/api";
import type { AdminProduct, Category, Paginated } from "@/lib/admin/types";
import ProductEditForm from "./ProductEditForm";

export const metadata = { title: "Edit product — Karivex Control Center" };

export default async function EditProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await getAdminToken();
  if (!token) return null;

  let product: AdminProduct;
  try {
    [product] = await Promise.all([adminGet<AdminProduct>(`/dashboard/products/${id}/`, token)]);
  } catch (e) {
    if (e instanceof AdminApiError && e.status === 404) notFound();
    throw e;
  }
  const categories = await adminGet<Paginated<Category>>("/dashboard/categories/?page_size=200", token);

  return (
    <>
      <h1>Edit product</h1>
      <p className="admin-page-lede">{product.name}</p>
      <ProductEditForm product={product} categories={categories.results} />
    </>
  );
}
