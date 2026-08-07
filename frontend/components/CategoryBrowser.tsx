"use client";
// The /categories grid, with a filter box.
//
// Client-side because the whole taxonomy is already in the page — 70-odd
// categories is nothing to filter in the browser, and it keeps the page
// statically rendered. Filtering matches sub-category names too, so typing
// "coagulant" surfaces the industry that contains it rather than nothing.

import { useState } from "react";
import Link from "next/link";
import type { CategoryTreeItem } from "@/lib/api";
// Shared with the server components that render this page — see the note in
// lib/categories.ts on why these must not live in a "use client" module.
import { childHasProducts, stockedCategories } from "@/lib/categories";

export default function CategoryBrowser({ industries }: { industries: CategoryTreeItem[] }) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  const stocked = stockedCategories(industries);
  const visible = !q
    ? stocked
    : stocked.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.description ?? "").toLowerCase().includes(q) ||
          c.children.some((k) => k.name.toLowerCase().includes(q)),
      );

  return (
    <>
      <div className="category-filter">
        <label htmlFor="category-filter-input">Filter categories</label>
        <input
          id="category-filter-input"
          type="search"
          value={query}
          placeholder="e.g. water treatment, solvents, coagulants…"
          onChange={(e) => setQuery(e.target.value)}
        />
        {q && (
          <p className="field-hint" role="status">
            {visible.length} of {stocked.length} categories match “{query.trim()}”.
          </p>
        )}
      </div>

      <div className="cat-index">
        {visible.map((c) => {
          // Sub-categories are filtered on the same rule, so an industry never
          // links down into an empty leaf.
          const children = c.children.filter(childHasProducts);
          return (
            <section key={c.slug} className="cat-index-group" aria-labelledby={`cat-${c.slug}`}>
              <h2 id={`cat-${c.slug}`}>
                <Link href={`/categories/${c.slug}`}>{c.name}</Link>
                <span className="cat-index-count">
                  {c.total_product_count} product{c.total_product_count === 1 ? "" : "s"}
                </span>
              </h2>
              {c.description && <p className="cat-index-desc">{c.description}</p>}
              {children.length > 0 && (
                <ul className="cat-index-subs">
                  {children.map((k) => (
                    <li key={k.slug}>
                      <Link href={`/categories/${k.slug}`}>{k.name}</Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>

      {visible.length === 0 && (
        <p className="search-empty">
          No category matches “{query.trim()}”.{" "}
          <Link href="/products">Browse all products</Link> or{" "}
          <Link href="/quote">ask us to source it</Link>.
        </p>
      )}
    </>
  );
}
