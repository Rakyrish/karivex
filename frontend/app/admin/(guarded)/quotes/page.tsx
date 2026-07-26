import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { AdminQuote, Paginated } from "@/lib/admin/types";
import { toggleHandledAction } from "./actions";

export const metadata = { title: "Quotes — Karivex Control Center" };

export default async function AdminQuotesPage({
  searchParams,
}: {
  searchParams: Promise<{ filter?: string }>;
}) {
  const { filter } = await searchParams;
  const token = await getAdminToken();
  if (!token) return null;

  const params = new URLSearchParams({ page_size: "100" });
  if (filter === "unhandled") params.set("handled", "false");
  const data = await adminGet<Paginated<AdminQuote>>(`/dashboard/quotes/?${params}`, token);

  return (
    <>
      <h1>Quote requests</h1>
      <p className="admin-page-lede">{data.count} request{data.count === 1 ? "" : "s"}{filter === "unhandled" ? " (unhandled only)" : ""}.</p>
      <div className="admin-section">
        <div className="admin-toolbar">
          <div className="row-actions">
            <a href="/admin/quotes" className={filter === "unhandled" ? "" : "link-btn"}>All</a>
            <a href="/admin/quotes?filter=unhandled" className={filter === "unhandled" ? "link-btn" : ""}>Unhandled only</a>
          </div>
        </div>
        <div className="admin-table-wrap">
          <table>
            <thead>
              <tr><th>Name</th><th>Company</th><th>Product</th><th>Qty</th><th>Country</th><th>Contact</th><th>Received</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {data.results.map((q) => (
                <tr key={q.id}>
                  <td className="wrap">{q.name}</td>
                  <td>{q.company || "—"}</td>
                  <td>{q.product_name ?? "General inquiry"}</td>
                  <td>{q.quantity}</td>
                  <td>{q.country}</td>
                  <td className="wrap">{q.email}<br />{q.phone}</td>
                  <td>{new Date(q.created_at).toLocaleDateString()}</td>
                  <td>
                    <span className={`badge ${q.handled ? "badge-handled" : "badge-unhandled"}`}>
                      {q.handled ? "Handled" : "Unhandled"}
                    </span>
                  </td>
                  <td>
                    <form action={toggleHandledAction.bind(null, q.id, !q.handled)}>
                      <button type="submit" className="link-btn">{q.handled ? "Mark unhandled" : "Mark handled"}</button>
                    </form>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && <tr><td colSpan={9}>No quote requests.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
