"use client";
import { useActionState, useState } from "react";
import type { Category } from "@/lib/admin/types";
import { createCategoryAction, updateCategoryAction, deleteCategoryAction, type CategoryFormState } from "./actions";

const emptyState: CategoryFormState = { error: null };

/** Shared by the edit and create forms so the two never drift apart. */
function CategoryFields({
  category, industries,
}: {
  category?: Category;
  industries: Category[];
}) {
  const [preview, setPreview] = useState<string | null>(category?.image ?? null);

  return (
    <>
      <div className="admin-form-grid">
        <label>Name <input name="name" defaultValue={category?.name} required /></label>
        <label>
          Parent industry <span className="field-hint">(blank = it IS an industry)</span>
          <select name="parent" defaultValue={category?.parent ?? ""}>
            <option value="">— Top-level industry —</option>
            {industries
              .filter((i) => i.id !== category?.id)
              .map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
        </label>
        <label>
          Menu order <span className="field-hint">(lower shows first)</span>
          <input name="display_order" type="number" defaultValue={category?.display_order ?? 0} />
        </label>
        <label>Meta title <input name="meta_title" defaultValue={category?.meta_title} maxLength={70} /></label>
      </div>

      <label>
        Tile image <span className="field-hint">(shown on the homepage industry card — landscape ~4:3)</span>
        <input
          name="image" type="file" accept="image/*"
          onChange={(e) => {
            const f = e.target.files?.[0];
            setPreview(f ? URL.createObjectURL(f) : (category?.image ?? null));
          }}
        />
      </label>
      {preview && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={preview} alt="" className="image-preview" />
      )}
      <label>Image alt text <input name="image_alt" defaultValue={category?.image_alt} maxLength={160} /></label>

      <label>Description <textarea name="description" rows={2} defaultValue={category?.description} /></label>
      <label>Meta description <textarea name="meta_description" rows={2} defaultValue={category?.meta_description} maxLength={160} /></label>
    </>
  );
}

function CategoryRow({ category, industries }: { category: Category; industries: Category[] }) {
  const bound = updateCategoryAction.bind(null, category.id);
  const [state, formAction, pending] = useActionState(bound, emptyState);
  const [open, setOpen] = useState(false);
  const parentName = industries.find((i) => i.id === category.parent)?.name;

  return (
    <>
      <tr id={`row-${category.id}`}>
        <td>
          {category.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={category.image} alt="" className="cat-thumb" />
          ) : (
            <span className="cat-thumb cat-thumb-empty" aria-label="No image">—</span>
          )}
        </td>
        <td className="wrap">
          {parentName ? <span className="cat-parent">{parentName} →</span> : null}
          {category.name}
        </td>
        <td>{category.product_count}</td>
        <td>{category.display_order}</td>
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
            <form action={formAction} className="admin-form" encType="multipart/form-data">
              <CategoryFields category={category} industries={industries} />
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
  const industries = categories.filter((c) => c.parent === null);

  return (
    <>
      <div className="admin-table-wrap">
        <table>
          <thead>
            <tr><th>Image</th><th>Name</th><th>Products</th><th>Order</th><th></th></tr>
          </thead>
          <tbody>
            {categories.map((c) => (
              <CategoryRow key={c.id} category={c} industries={industries} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="admin-form-section-title">Add a category</div>
      <form action={createFormAction} className="admin-form" encType="multipart/form-data">
        <CategoryFields industries={industries} />
        <div className="admin-form-actions">
          <button type="submit" className="cta" disabled={creating}>{creating ? "Adding…" : "Add category"}</button>
          {createState.error && <span className="admin-form-error" role="alert">{createState.error}</span>}
        </div>
      </form>
    </>
  );
}
