"use client";
import { useActionState, useState } from "react";
import type { AdminBlogPost, AdminProductListItem } from "@/lib/admin/types";
import SerpPreview from "../../components/SerpPreview";
import { createBlogAction, updateBlogAction, type BlogFormState } from "./actions";

const emptyState: BlogFormState = { error: null };

export default function BlogForm({
  post, products,
}: {
  post?: AdminBlogPost; products: AdminProductListItem[];
}) {
  const action = post ? updateBlogAction.bind(null, post.id) : createBlogAction;
  const [state, formAction, pending] = useActionState(action, emptyState);
  const [metaTitle, setMetaTitle] = useState(post?.meta_title ?? "");
  const [metaDescription, setMetaDescription] = useState(post?.meta_description ?? "");

  return (
    <form action={formAction} className="admin-section" encType="multipart/form-data">
      <h2>{post ? "Edit post" : "New post"}</h2>
      <div className="admin-form">
        <label>Title <input name="title" defaultValue={post?.title} required /></label>
        <label>Excerpt <span className="field-hint">(used as list preview and meta description fallback)</span>
          <textarea name="excerpt" rows={2} defaultValue={post?.excerpt} maxLength={300} required />
        </label>
        <label>Body <span className="field-hint">(Markdown)</span>
          <textarea name="body" rows={12} defaultValue={post?.body} required />
        </label>

        <label>
          Meta title
          <span className={`char-counter ${metaTitle.length > 70 ? "over" : ""}`}>{metaTitle.length}/70</span>
          <input name="meta_title" value={metaTitle} onChange={(e) => setMetaTitle(e.target.value)} maxLength={70} />
        </label>
        <label>
          Meta description
          <span className={`char-counter ${metaDescription.length > 160 ? "over" : ""}`}>{metaDescription.length}/160</span>
          <textarea name="meta_description" rows={2} value={metaDescription} onChange={(e) => setMetaDescription(e.target.value)} maxLength={160} />
        </label>
        <SerpPreview title={metaTitle} description={metaDescription} url={`karivex.co.ke/blog/${post?.slug ?? "post-slug"}`} />

        <label>Cover image {post?.cover_image && <span className="field-hint">(leave blank to keep current)</span>}
          <input type="file" name="cover_image" accept="image/*" />
        </label>
        {post?.cover_image && <img src={post.cover_image} alt={post.cover_image_alt} style={{ maxWidth: 200, borderRadius: 8 }} />}
        <label>Cover image alt <input name="cover_image_alt" defaultValue={post?.cover_image_alt} maxLength={160} /></label>

        <label>Related products <span className="field-hint">(ctrl/cmd-click to select multiple)</span>
          <select name="related_products" multiple size={6} defaultValue={post?.related_products.map(String)}>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>

        <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
          <input type="checkbox" name="published" value="true" defaultChecked={post?.published} /> Published
        </label>

        <div className="admin-form-actions">
          <button type="submit" className="cta" disabled={pending}>
            {pending ? "Saving…" : post ? "Save changes" : "Create post"}
          </button>
          {state.error && <span className="admin-form-error" role="alert">{state.error}</span>}
        </div>
      </div>
    </form>
  );
}
