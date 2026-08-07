// Catalogue search.
//
// Runs over the product list the site already fetches for its static params,
// rather than through a search API. With ~180 products the whole index is a
// few kilobytes, so matching is instant, works on a statically rendered page,
// and adds no backend surface to secure or rate-limit. If the catalogue grows
// past a few thousand products this should move server-side — the matcher
// below is deliberately the only thing that would need to change.

import type { ProductListItem } from "./api";

export interface SearchHit {
  product: ProductListItem;
  /** Why it matched, shown to the buyer so a CAS or synonym hit isn't baffling. */
  reason: string;
}

function normalise(text: string): string {
  return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
}

/** CAS numbers are typed with or without hyphens; strip everything but digits
 *  so "7647017" still finds "7647-01-7". */
function digits(text: string): string {
  return (text || "").replace(/\D+/g, "");
}

export function searchProducts(products: ProductListItem[], query: string): SearchHit[] {
  const q = normalise(query);
  if (q.length < 2) return [];
  const qDigits = digits(q);
  const terms = q.split(" ").filter(Boolean);

  const hits: Array<SearchHit & { rank: number }> = [];

  for (const product of products) {
    const name = normalise(product.name);
    const synonyms = normalise(product.synonyms ?? "");
    const cas = product.cas_number ?? "";
    const category = normalise(product.category_name ?? product.category_slug ?? "");

    let rank = 0;
    let reason = "";

    // Ranked most-specific first, so an exact name beats a category brush.
    if (name === q) { rank = 100; reason = ""; }
    else if (qDigits.length >= 5 && digits(cas) === qDigits) { rank = 95; reason = `CAS ${cas}`; }
    else if (name.startsWith(q)) { rank = 80; reason = ""; }
    else if (name.includes(q)) { rank = 70; reason = ""; }
    else if (synonyms.includes(q)) { rank = 60; reason = "Also known as"; }
    else if (category.includes(q)) { rank = 40; reason = product.category_name ?? ""; }
    else if (terms.length > 1 && terms.every((t) => name.includes(t) || synonyms.includes(t))) {
      rank = 50;
      reason = "";
    }

    if (rank > 0) hits.push({ product, reason, rank });
  }

  return hits
    .sort((a, b) => b.rank - a.rank || a.product.name.localeCompare(b.product.name))
    .map(({ product, reason }) => ({ product, reason }));
}
