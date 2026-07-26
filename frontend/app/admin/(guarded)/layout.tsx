import { redirect } from "next/navigation";
import { getAdminToken } from "@/lib/admin/session";
import Sidebar from "../components/Sidebar";
import { logoutAction } from "./logout/actions";

const API = process.env.INTERNAL_API_URL ?? "http://karivex_backend:8000";

type Me = { username: string; email: string; is_superuser: boolean };
type Stats = { quotes: { unhandled: number }; orders: { pending: number } };

export default async function GuardedLayout({ children }: { children: React.ReactNode }) {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  const headers = { Authorization: `Bearer ${token}` };
  const [meRes, statsRes] = await Promise.all([
    fetch(`${API}/api/dashboard/auth/me/`, { headers, cache: "no-store" }),
    fetch(`${API}/api/dashboard/stats/`, { headers, cache: "no-store" }),
  ]);

  if (meRes.status === 401) redirect("/admin/login");
  if (!meRes.ok) throw new Error("Admin service unavailable — please try again shortly.");

  const me: Me = await meRes.json();
  const stats: Stats | null = statsRes.ok ? await statsRes.json() : null;

  return (
    <div className="admin-shell">
      <Sidebar unhandledQuotes={stats?.quotes.unhandled ?? 0} pendingOrders={stats?.orders.pending ?? 0} />
      <div className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar-user">
            Signed in as <strong>{me.username}</strong>
          </div>
          <form action={logoutAction}>
            <button type="submit" className="cta-ghost">Log out</button>
          </form>
        </header>
        <main className="admin-content">{children}</main>
      </div>
    </div>
  );
}
