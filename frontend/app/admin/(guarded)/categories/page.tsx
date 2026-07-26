import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { Category, Paginated } from "@/lib/admin/types";
import CategoryTable from "./CategoryTable";

export const metadata = { title: "Categories — Karivex Control Center" };

export default async function AdminCategoriesPage() {
  const token = await getAdminToken();
  if (!token) return null;

  const data = await adminGet<Paginated<Category>>("/dashboard/categories/?page_size=200", token);

  return (
    <>
      <h1>Categories</h1>
      <p className="admin-page-lede">{data.count} categor{data.count === 1 ? "y" : "ies"}.</p>
      <div className="admin-section">
        <CategoryTable categories={data.results} />
      </div>
    </>
  );
}
