"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import type { CategoryTreeItem, ProductListItem } from "@/lib/api";
import ProductCardActions, { type CardContact } from "@/components/ProductCardActions";

/** Per-industry tabbed product grids.
 *
 * Products sit on the leaf category they belong to, but buyers browse by
 * industry — so a product filed under "Solvents & Thinners" has to surface
 * under its parent industry "Paints, Inks & Coatings" too. That roll-up is
 * done here rather than server-side so one products fetch serves every tab.
 * Industries with nothing in them are dropped instead of rendering an empty
 * grid.
 */
export default function IndustryTabs({
  industries,
  products,
  // Passed in rather than read from lib/site: this is a client component and
  // those env vars do not exist in the browser bundle.
  contact,
}: {
  industries: CategoryTreeItem[];
  products: ProductListItem[];
  contact: CardContact;
}) {
  const grouped = useMemo(() => {
    // slug of any category (industry or sub) -> owning industry id
    const owner = new Map<string, number>();
    for (const ind of industries) {
      owner.set(ind.slug, ind.id);
      for (const child of ind.children) owner.set(child.slug, ind.id);
    }
    const byIndustry = new Map<number, ProductListItem[]>();
    for (const p of products) {
      const id = owner.get(p.category_slug);
      if (id === undefined) continue;
      const list = byIndustry.get(id);
      if (list) list.push(p);
      else byIndustry.set(id, [p]);
    }
    return industries
      .map((ind) => ({ industry: ind, items: byIndustry.get(ind.id) ?? [] }))
      .filter((g) => g.items.length > 0);
  }, [industries, products]);

  const [activeId, setActiveId] = useState<number | null>(null);
  if (grouped.length === 0) return null;

  const active = grouped.find((g) => g.industry.id === activeId) ?? grouped[0];

  return (
    <section className="industry-tabs" aria-labelledby="browse-by-industry">
      <div className="industry-tabs-head">
        <h2 id="browse-by-industry">Browse by industry</h2>
        <div className="industry-tabs-list" role="tablist" aria-label="Industries">
          {grouped.map(({ industry, items }) => (
            <button
              key={industry.id}
              type="button"
              role="tab"
              aria-selected={industry.id === active.industry.id}
              className={industry.id === active.industry.id ? "is-active" : ""}
              onClick={() => setActiveId(industry.id)}
            >
              {industry.name}
              <span>{items.length}</span>
            </button>
          ))}
        </div>
      </div>

      <ul className="product-grid">
        {active.items.slice(0, 8).map((p) => (
          <li key={p.slug} className="product-card">
            <Link href={`/products/${p.slug}`}>
              {p.image && (
                <Image src={p.image} alt={p.image_alt} width={300} height={200}
                       style={{ width: "100%", height: "auto" }} />
              )}
              <h3>{p.name}</h3>
              <p>{[p.purity, p.packaging].filter(Boolean).join(" · ")}</p>
              {p.is_small_pack && p.price_kes && <p>From KES {p.price_kes}</p>}
            </Link>
            <ProductCardActions productName={p.name} contact={contact} />
          </li>
        ))}
      </ul>

      <p className="industry-tabs-more">
        <Link href={`/categories/${active.industry.slug}`}>
          View all {active.industry.name} &rarr;
        </Link>
      </p>
    </section>
  );
}
