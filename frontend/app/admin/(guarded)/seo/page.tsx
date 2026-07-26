import Link from "next/link";
import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { SeoAudit, SeoIssue } from "@/lib/admin/types";
import SeoGauge from "../../components/SeoGauge";

export const metadata = { title: "SEO Health — Karivex Control Center" };

function editLinkFor(issue: SeoIssue) {
  if (issue.type === "product") return `/admin/products/${issue.id}/edit`;
  if (issue.type === "blog") return `/admin/blog/${issue.id}/edit`;
  return `/admin/categories#row-${issue.id}`;
}

export default async function AdminSeoPage() {
  const token = await getAdminToken();
  if (!token) return null;

  const audit = await adminGet<SeoAudit>("/dashboard/seo-audit/", token);

  const groups: Record<string, SeoIssue[]> = { product: [], category: [], blog: [] };
  for (const issue of audit.issues) groups[issue.type].push(issue);

  return (
    <>
      <h1>SEO Health</h1>
      <p className="admin-page-lede">
        Live audit across every product, category and published blog post — recomputed fresh on every visit.
        Checked {new Date(audit.checked_at).toLocaleString()}.
      </p>

      <div className="seo-health-card">
        <SeoGauge score={audit.score} />
        <div className="seo-health-body">
          <h2>{audit.issue_count} issue{audit.issue_count === 1 ? "" : "s"} found</h2>
          {audit.issue_count === 0 && <p>Everything checks out — no missing metadata, alt text, or thin descriptions.</p>}
        </div>
      </div>

      {(["product", "category", "blog"] as const).map((type) =>
        groups[type].length > 0 && (
          <div className="admin-section" key={type}>
            <h2 style={{ textTransform: "capitalize" }}>{type}s ({groups[type].length})</h2>
            <div className="admin-table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Field</th><th>Issue</th><th></th></tr></thead>
                <tbody>
                  {groups[type].map((issue, i) => (
                    <tr key={i}>
                      <td className="wrap">{issue.name}</td>
                      <td>{issue.field}</td>
                      <td className="wrap">{issue.issue}</td>
                      <td><Link href={editLinkFor(issue)} className="link-btn">Fix →</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      )}
    </>
  );
}
