import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { Category, Paginated } from "@/lib/admin/types";
import ProductWizard from "./ProductWizard";

export const metadata = { title: "Add product — Karivex Control Center" };

export default async function NewProductPage() {
  const token = await getAdminToken();
  if (!token) return null;

  const categories = await adminGet<Paginated<Category>>("/dashboard/categories/?page_size=200", token);

  return (
    <>
      <div className="new-product-hero">
        <h1>Add a product</h1>
        <p className="admin-page-lede">
          Paste a product URL and AI drafts the whole listing — specs, copy, FAQs and
          search metadata — for you to review. Nothing is saved until you publish.
        </p>
      </div>
      <ProductWizard categories={categories.results} />
    </>
  );
}
