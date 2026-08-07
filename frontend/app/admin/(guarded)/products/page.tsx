import Link from "next/link";
import Image from "next/image";
import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { AdminProductListItem, Paginated } from "@/lib/admin/types";
import BulkGeneratePanel from "./BulkGeneratePanel";

export const metadata = { title: "Products — Karivex Control Center" };

export default async function AdminProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; page?: string }>;
}) {
  const { q, page } = await searchParams;
  const token = await getAdminToken();
  if (!token) return null;

  const params = new URLSearchParams();
  if (q) params.set("search", q);
  params.set("page", page ?? "1");
  params.set("page_size", "25");

  const data = await adminGet<Paginated<AdminProductListItem>>(`/dashboard/products/?${params}`, token);

  return (
    <>
      <h1>Products</h1>
      <p className="admin-page-lede">{data.count} product{data.count === 1 ? "" : "s"} in the catalog.</p>

      <BulkGeneratePanel />

      <div className="admin-section">
        <div className="admin-toolbar">
          <form method="get">
            <input type="search" name="q" placeholder="Search by name, CAS number, synonyms…" defaultValue={q ?? ""} />
            <button type="submit" className="btn-secondary">Search</button>
          </form>
          <Link href="/admin/products/new" className="cta">+ Add product with AI</Link>
        </div>

        <div className="admin-table-wrap">
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Name</th>
                <th>Category</th>
                <th>Price (KES)</th>
                <th>Stock</th>
                <th>Featured</th>
                <th>Updated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((p) => (
                <tr key={p.id}>
                  <td>
                    {p.image ? (
                      <Image src={p.image} alt="" width={36} height={36} style={{ borderRadius: 6, objectFit: "cover" }} />
                    ) : (
                      <span className="badge badge-navy">no img</span>
                    )}
                  </td>
                  <td className="wrap">{p.name}</td>
                  <td>{p.category_name}</td>
                  <td>{p.price_kes ?? "Quote only"}</td>
                  <td>
                    <span className={`badge ${p.in_stock ? "badge-in-stock" : "badge-out-of-stock"}`}>
                      {p.in_stock ? "In stock" : "Out of stock"}
                    </span>
                  </td>
                  <td>{p.featured ? "★" : ""}</td>
                  <td>{new Date(p.updated_at).toLocaleDateString()}</td>
                  <td>
                    <Link href={`/admin/products/${p.id}/edit`} className="link-btn">Edit</Link>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr><td colSpan={8}>No products found.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          {data.previous ? (
            <Link href={`?${new URLSearchParams({ ...(q ? { q } : {}), page: String(Number(page ?? "1") - 1) })}`}>← Previous</Link>
          ) : <span />}
          {data.next ? (
            <Link href={`?${new URLSearchParams({ ...(q ? { q } : {}), page: String(Number(page ?? "1") + 1) })}`}>Next →</Link>
          ) : <span />}
        </div>
      </div>
    </>
  );
}
