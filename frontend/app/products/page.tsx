import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getProductsPage, SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";
import { ORG_ID, jsonLd } from "@/lib/schema";
import ProductCardActions from "@/components/ProductCardActions";

// Must be generateMetadata, not a static `metadata` export: the canonical has
// to vary with ?page. Previously every page in the series canonicalised to
// /products, which tells Google that pages 2-10 are duplicates of page 1 — so
// it stops crawling them, and the 132 products that live only on those pages
// lose their one internal discovery path. Paginated pages self-canonicalise;
// only the page-1 URL is advertised in the sitemap.
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const canonical = page > 1 ? `${SITE_URL}/products?page=${page}` : `${SITE_URL}/products`;
  const title = page > 1 ? `All Products — page ${page} | ${site.shortName}` : `All Products | ${site.shortName}`;
  const description =
    page > 1
      ? `Page ${page} of the full ${site.name} catalogue — industrial, food-grade, laboratory and specialty chemicals supplied across East Africa.`
      : `Browse the full ${site.name} catalogue — industrial, food-grade, laboratory and specialty chemicals supplied across East Africa.`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      type: "website",
      url: canonical,
      images: [{ url: `${SITE_URL}/og?type=products&title=${encodeURIComponent("All Products")}`, width: 1200, height: 630 }],
    },
  };
}

type Props = { searchParams: Promise<{ page?: string }> };

export default async function ProductsIndexPage({ searchParams }: Props) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const { results, hasNext, hasPrevious, outOfRange } = await getProductsPage(page);

  // ?page=N past the end of the series was answering 200 with a unique title,
  // a self-referencing canonical and an empty grid — for every N. That is an
  // unbounded supply of indexable near-identical empty pages hanging off one
  // crawlable URL, and it is the same soft-404 failure the sitemap already
  // works to avoid for empty categories: Google crawls page=99, page=100, …
  // indefinitely, spends the budget there instead of on the 181 real products,
  // and files what it finds under "Soft 404" / "Crawled – currently not
  // indexed". A 404 is the honest answer and closes the space outright, which
  // noindex would not — noindex still has to be crawled to be seen.
  //
  // Guarded on two conditions, both necessary. `page > 1` keeps /products
  // itself reachable no matter what the API says, and `outOfRange` fires only
  // on a definitive 404 from DRF — never on a transport error or a 5xx. An
  // outage therefore still renders the empty-state copy below rather than
  // 404ing the catalogue index out of the index, which would be far more
  // damaging than the problem being fixed here.
  if (page > 1 && outOfRange) notFound();

  // The catalogue index shipped a lone BreadcrumbList and nothing else, so the
  // one page that lists every product told a crawler nothing about what it
  // lists. A CollectionPage carrying a named ItemList gives each paginated
  // slice an explicit inventory, and `@id` is page-scoped so page 2's list is
  // never merged with page 1's.
  const canonical = page > 1 ? `${SITE_URL}/products?page=${page}` : `${SITE_URL}/products`;
  const listId = `${canonical}#products`;
  const breadcrumbId = `${SITE_URL}/products#breadcrumb`;

  const catalogueGraph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": canonical,
        url: canonical,
        name: page > 1 ? `All Products — page ${page}` : "All Products",
        description: `The full ${site.name} catalogue — industrial, food-grade, laboratory and specialty chemicals supplied across East Africa.`,
        inLanguage: "en-KE",
        isPartOf: { "@id": `${SITE_URL}/#website` },
        breadcrumb: { "@id": breadcrumbId },
        publisher: { "@id": ORG_ID },
        ...(results.length > 0 && { mainEntity: { "@id": listId } }),
      },
      {
        "@type": "BreadcrumbList",
        "@id": breadcrumbId,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Products", item: `${SITE_URL}/products` },
        ],
      },
      ...(results.length > 0
        ? [
            {
              "@type": "ItemList",
              "@id": listId,
              name: `${site.shortName} chemical catalogue${page > 1 ? ` — page ${page}` : ""}`,
              numberOfItems: results.length,
              itemListOrder: "https://schema.org/ItemListUnordered",
              itemListElement: results.map((p, i) => ({
                "@type": "ListItem",
                position: i + 1,
                name: p.name,
                url: `${SITE_URL}/products/${p.slug}`,
              })),
            },
          ]
        : []),
    ],
  };

  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(catalogueGraph) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <span aria-current="page">Products</span>
      </nav>

      <h1>All products</h1>
      <p className="lede">
        The full {site.shortName} catalogue — bulk and small-pack chemicals across every grade we supply. Browse
        by <Link href="/#categories">category</Link> instead if you know what you&rsquo;re looking for.
      </p>

      {results.length === 0 ? (
        <p>No products published yet — check back soon, or <Link href="/quote">request a quote</Link> directly.</p>
      ) : (
        <ul className="product-grid">
          {results.map((p) => (
            <li key={p.slug} className="product-card">
              <Link href={`/products/${p.slug}`}>
                {p.image && (
                  <Image
                    src={p.image}
                    alt={p.image_alt}
                    width={300}
                    height={200}
                    style={{ width: "100%", height: "auto" }}
                  />
                )}
                <h2>{p.name}</h2>
                <p>{p.purity} · {p.packaging}</p>
                {p.is_small_pack && p.price_kes && <p>From KES {p.price_kes}</p>}
              </Link>
              <ProductCardActions productName={p.name} contact={site} />
            </li>
          ))}
        </ul>
      )}

      <nav className="pagination" aria-label="Product pagination">
        {hasPrevious && <Link href={`/products?page=${page - 1}`}>&larr; Previous</Link>}
        {hasNext && <Link href={`/products?page=${page + 1}`}>Next &rarr;</Link>}
      </nav>
    </section>
  );
}
