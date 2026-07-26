import Link from "next/link";
import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { Stats, SeoAudit } from "@/lib/admin/types";
import SeoGauge from "../components/SeoGauge";

export const metadata = { title: "Dashboard — Karivex Control Center" };

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function editLinkFor(issue: { type: string; id: number }) {
  if (issue.type === "product") return `/admin/products/${issue.id}/edit`;
  if (issue.type === "blog") return `/admin/blog/${issue.id}/edit`;
  return `/admin/categories#row-${issue.id}`;
}

export default async function AdminDashboardPage() {
  const token = await getAdminToken();
  if (!token) return null; // layout already redirects; keeps TS happy

  const [stats, audit] = await Promise.all([
    adminGet<Stats>("/dashboard/stats/", token),
    adminGet<SeoAudit>("/dashboard/seo-audit/", token),
  ]);

  const revenue = Number(stats.orders.revenue_kes || 0);

  return (
    <>
      <h1>Dashboard</h1>
      <p className="admin-page-lede">Live operational overview — every number here is read straight from the database.</p>

      <div className="quick-actions">
        <Link href="/admin/products/new" className="cta">+ Add product with AI</Link>
        <Link href="/admin/blog/new" className="cta-ghost" style={{ color: "var(--navy-800)", border: "1.5px solid var(--rule)" }}>+ New blog post</Link>
        <Link href="/admin/quotes" className="cta-ghost" style={{ color: "var(--navy-800)", border: "1.5px solid var(--rule)" }}>Review quotes</Link>
        <Link href="/admin/orders" className="cta-ghost" style={{ color: "var(--navy-800)", border: "1.5px solid var(--rule)" }}>View orders</Link>
      </div>

      <div className="kpi-row">
        <div className="kpi-tile">
          <div className="kpi-tile-label">Products</div>
          <div className="kpi-tile-value">{stats.products.total}</div>
          <div className="kpi-tile-sub">{stats.products.in_stock_count} in stock · {stats.products.featured_count} featured</div>
        </div>
        <div className="kpi-tile kpi-navy">
          <div className="kpi-tile-label">Categories</div>
          <div className="kpi-tile-value">{stats.categories.total}</div>
        </div>
        <div className="kpi-tile kpi-teal">
          <div className="kpi-tile-label">Blog posts</div>
          <div className="kpi-tile-value">{stats.blog.published_count}</div>
          <div className="kpi-tile-sub">{stats.blog.draft_count} draft{stats.blog.draft_count === 1 ? "" : "s"}</div>
        </div>
        <div className={`kpi-tile ${stats.quotes.unhandled > 0 ? "kpi-alert" : "kpi-teal"}`}>
          <div className="kpi-tile-label">Quote requests</div>
          <div className="kpi-tile-value">{stats.quotes.total}</div>
          <div className={`kpi-tile-sub ${stats.quotes.unhandled > 0 ? "warn" : ""}`}>
            {stats.quotes.unhandled} unhandled · {stats.quotes.last_7_days} this week
          </div>
        </div>
        <div className={`kpi-tile ${stats.orders.pending > 0 ? "kpi-alert" : "kpi-teal"}`}>
          <div className="kpi-tile-label">Orders</div>
          <div className="kpi-tile-value">{stats.orders.total}</div>
          <div className="kpi-tile-sub">{stats.orders.pending} pending</div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-tile-label">Revenue (paid + delivered)</div>
          <div className="kpi-tile-value">KES {revenue.toLocaleString()}</div>
        </div>
      </div>

      <div className="seo-health-card">
        <SeoGauge score={audit.score} />
        <div className="seo-health-body">
          <h2>SEO Health</h2>
          {audit.issues.length === 0 ? (
            <p>No issues found — every product, category and published post passes the checklist.</p>
          ) : (
            <>
              <p>{audit.issue_count} issue{audit.issue_count === 1 ? "" : "s"} found across products, categories and blog posts.</p>
              <ul className="seo-issue-list">
                {audit.issues.slice(0, 3).map((issue, i) => (
                  <li key={i}>
                    <span className="seo-issue-tag">{issue.type}</span>
                    <Link href={editLinkFor(issue)}>{issue.name}</Link> — {issue.issue}
                  </li>
                ))}
              </ul>
            </>
          )}
          <Link href="/admin/seo">View full SEO audit →</Link>
        </div>
      </div>

      <div className="activity-card">
        <h2>Recent activity</h2>
        {stats.recent_activity.length === 0 ? (
          <p>No quote requests or orders yet.</p>
        ) : (
          <ul className="activity-list">
            {stats.recent_activity.map((a) => (
              <li key={`${a.type}-${a.id}`}>
                <span className={`activity-kind activity-kind-${a.type}`}>{a.type}</span>
                <span className="activity-summary">{a.summary}</span>
                <span className="activity-time">{timeAgo(a.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
