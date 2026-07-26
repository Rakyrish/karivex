"use client";
import { useActionState, useState } from "react";
import type { Category } from "@/lib/admin/types";
import { createCategoryAction, updateCategoryAction, deleteCategoryAction, type CategoryFormState } from "./actions";

const emptyState: CategoryFormState = { error: null };

function CategoryRow({ category }: { category: Category }) {
  const bound = updateCategoryAction.bind(null, category.id);
  const [state, formAction, pending] = useActionState(bound, emptyState);
  const [open, setOpen] = useState(false);

  return (
    <>
      <tr id={`row-${category.id}`}>
        <td className="wrap">{category.name}</td>
        <td>{category.slug}</td>
        <td>{category.product_count}</td>
        <td className="wrap">{category.meta_title || <em>auto-generated</em>}</td>
        <td>
          <div className="row-actions">
            <button type="button" className="link-btn" onClick={() => setOpen((o) => !o)}>{open ? "Close" : "Edit"}</button>
            <button
              type="button" className="link-btn"
              onClick={() => { if (confirm(`Delete category "${category.name}"?`)) deleteCategoryAction(category.id); }}
            >
              Delete
            </button>
          </div>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5}>
            <form action={formAction} className="admin-form">
              <div className="admin-form-grid">
                <label>Name <input name="name" defaultValue={category.name} required /></label>
                <label>Meta title <input name="meta_title" defaultValue={category.meta_title} maxLength={70} /></label>
              </div>
              <label>Description <textarea name="description" rows={2} defaultValue={category.description} /></label>
              <label>Meta description <textarea name="meta_description" rows={2} defaultValue={category.meta_description} maxLength={160} /></label>
              <div className="admin-form-actions">
                <button type="submit" className="cta" disabled={pending}>{pending ? "Saving…" : "Save"}</button>
                {state.error && <span className="admin-form-error" role="alert">{state.error}</span>}
              </div>
            </form>
          </td>
        </tr>
      )}
    </>
  );
}

export default function CategoryTable({ categories }: { categories: Category[] }) {
  const [createState, createFormAction, creating] = useActionState(createCategoryAction, emptyState);

  return (
    <>
      <div className="admin-table-wrap">
        <table>
          <thead>
            <tr><th>Name</th><th>Slug</th><th>Products</th><th>Meta title</th><th></th></tr>
          </thead>
          <tbody>
            {categories.map((c) => <CategoryRow key={c.id} category={c} />)}
          </tbody>
        </table>
      </div>

      <div className="admin-form-section-title">Add a category</div>
      <form action={createFormAction} className="admin-form">
        <div className="admin-form-grid">
          <label>Name <input name="name" required /></label>
          <label>Meta title <span className="field-hint">(optional — auto-generated if blank)</span><input name="meta_title" maxLength={70} /></label>
        </div>
        <label>Description <textarea name="description" rows={2} /></label>
        <label>Meta description <textarea name="meta_description" rows={2} maxLength={160} /></label>
        <div className="admin-form-actions">
          <button type="submit" className="cta" disabled={creating}>{creating ? "Adding…" : "Add category"}</button>
          {createState.error && <span className="admin-form-error" role="alert">{createState.error}</span>}
        </div>
      </form>
    </>
  );
}
