import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { AdminOrder, Paginated } from "@/lib/admin/types";
import { updateOrderStatusAction } from "./actions";

export const metadata = { title: "Orders — Karivex Control Center" };

const STATUSES = ["pending", "paid", "delivered", "cancelled"] as const;

export default async function AdminOrdersPage() {
  const token = await getAdminToken();
  if (!token) return null;

  const data = await adminGet<Paginated<AdminOrder>>("/dashboard/orders/?page_size=100", token);

  return (
    <>
      <h1>Orders</h1>
      <p className="admin-page-lede">{data.count} order{data.count === 1 ? "" : "s"}.</p>
      <div className="admin-section">
        <div className="admin-table-wrap">
          <table>
            <thead>
              <tr><th>Customer</th><th>Product</th><th>Qty</th><th>Amount (KES)</th><th>Phone</th><th>Placed</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {data.results.map((o) => (
                <tr key={o.id}>
                  <td className="wrap">{o.customer_name}</td>
                  <td>{o.product_name}</td>
                  <td>{o.quantity}</td>
                  <td>{Number(o.amount_kes).toLocaleString()}</td>
                  <td>{o.phone}</td>
                  <td>{new Date(o.created_at).toLocaleDateString()}</td>
                  <td>
                    <span className={`badge ${o.status === "cancelled" ? "badge-out-of-stock" : o.status === "pending" ? "badge-unhandled" : "badge-handled"}`}>
                      {o.status}
                    </span>
                  </td>
                  <td>
                    <form action={updateOrderStatusAction.bind(null, o.id)} className="row-actions">
                      <select name="status" defaultValue={o.status} className="status-select">
                        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                      <button type="submit" className="link-btn">Update</button>
                    </form>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && <tr><td colSpan={8}>No orders yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
