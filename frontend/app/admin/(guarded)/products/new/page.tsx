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
      <h1>Add a product</h1>
      <p className="admin-page-lede">
        Enter the facts, generate a draft with OpenAI, review and edit it, then publish.
        Nothing is saved until you click Create Product.
      </p>
      <ProductWizard categories={categories.results} />
    </>
  );
}
