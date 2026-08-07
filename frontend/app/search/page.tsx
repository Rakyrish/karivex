import type { Metadata } from "next";
import Link from "next/link";
import { getProducts, SITE_URL } from "@/lib/api";
import { searchProducts } from "@/lib/search";
import { site } from "@/lib/site";

// Search result pages must never be indexed. Google treats indexable internal
// search results as thin, near-duplicate content and it is an explicit item in
// their quality guidelines — one indexable ?q= parameter can generate an
// unbounded set of low-value URLs. `follow` is kept so the product links here
// still pass equity.
export const metadata: Metadata = {
  title: `Search the catalogue | ${site.shortName}`,
  description: `Search ${site.name}'s chemical catalogue by product name, CAS number or synonym.`,
  robots: { index: false, follow: true },
  alternates: { canonical: `${SITE_URL}/search` },
};

type Props = { searchParams: Promise<{ q?: string }> };

export default async function SearchPage({ searchParams }: Props) {
  const { q = "" } = await searchParams;
  const query = q.trim();
  const products = await getProducts();
  const hits = query ? searchProducts(products, query) : [];

  return (
    <article className="search-page">
      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <span aria-current="page">Search</span>
      </nav>

      <h1>{query ? `Search results for “${query}”` : "Search the catalogue"}</h1>

      {!query && (
        <p className="lede">
          Search by product name, CAS number or an alternative name — for example{" "}
          <Link href="/search?q=caustic">caustic</Link> or{" "}
          <Link href="/search?q=7647-01-0">7647-01-0</Link>.
        </p>
      )}

      {query && (
        <p className="lede">
          {hits.length === 0
            ? "No products matched."
            : `${hits.length} product${hits.length === 1 ? "" : "s"} matched.`}
        </p>
      )}

      {hits.length > 0 && (
        <ul className="search-results">
          {hits.map(({ product, reason }) => (
            <li key={product.slug}>
              <Link href={`/products/${product.slug}`}>
                <strong>{product.name}</strong>
                <span className="search-result-meta">
                  {[reason, product.purity, product.packaging].filter(Boolean).join(" · ")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {/* A dead end is where a buyer leaves. Every zero-result search offers
          the two routes that still convert: browse, or ask us to source it. */}
      {query && hits.length === 0 && (
        <div className="search-empty">
          <p>
            We may still supply it — much of the catalogue is sourced to order and not every
            synonym is listed.
          </p>
          <p>
            <Link href="/quote" className="cta">Ask us to source it</Link>{" "}
            or <Link href="/products">browse all products</Link>.
          </p>
        </div>
      )}
    </article>
  );
}
