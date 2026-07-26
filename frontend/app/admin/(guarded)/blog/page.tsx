import Link from "next/link";
import { getAdminToken } from "@/lib/admin/session";
import { adminGet } from "@/lib/admin/api";
import type { AdminBlogPost, Paginated } from "@/lib/admin/types";
import { deleteBlogAction } from "./actions";
import ConfirmDeleteButton from "../../components/ConfirmDeleteButton";

export const metadata = { title: "Blog — Karivex Control Center" };

export default async function AdminBlogPage() {
  const token = await getAdminToken();
  if (!token) return null;

  const data = await adminGet<Paginated<AdminBlogPost>>("/dashboard/blog/?page_size=100", token);

  return (
    <>
      <h1>Blog</h1>
      <p className="admin-page-lede">{data.count} post{data.count === 1 ? "" : "s"}.</p>
      <div className="admin-section">
        <div className="admin-toolbar">
          <span />
          <Link href="/admin/blog/new" className="cta">+ New post</Link>
        </div>
        <div className="admin-table-wrap">
          <table>
            <thead><tr><th>Title</th><th>Status</th><th>Updated</th><th></th></tr></thead>
            <tbody>
              {data.results.map((p) => (
                <tr key={p.id}>
                  <td className="wrap">{p.title}</td>
                  <td>
                    <span className={`badge ${p.published ? "badge-in-stock" : "badge-navy"}`}>
                      {p.published ? "Published" : "Draft"}
                    </span>
                  </td>
                  <td>{new Date(p.updated_at).toLocaleDateString()}</td>
                  <td>
                    <div className="row-actions">
                      <Link href={`/admin/blog/${p.id}/edit`} className="link-btn">Edit</Link>
                      <ConfirmDeleteButton action={deleteBlogAction.bind(null, p.id)} confirmText={`Delete "${p.title}"?`} />
                    </div>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && <tr><td colSpan={4}>No posts yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
