import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { getProductsPage, SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: `All Products | ${site.shortName}`,
  description: `Browse the full ${site.name} catalogue — industrial, food-grade, laboratory, pharmaceutical and cosmetic-grade chemicals supplied across ${site.regions.join(", ")}.`,
  alternates: { canonical: `${SITE_URL}/products` },
  openGraph: {
    title: `All Products | ${site.shortName}`,
    type: "website",
    url: `${SITE_URL}/products`,
    images: [{ url: `${SITE_URL}/og?type=products&title=${encodeURIComponent("All Products")}`, width: 1200, height: 630 }],
  },
};

const breadcrumbSchema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
    { "@type": "ListItem", position: 2, name: "Products", item: `${SITE_URL}/products` },
  ],
};

type Props = { searchParams: Promise<{ page?: string }> };

export default async function ProductsIndexPage({ searchParams }: Props) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const { results, hasNext, hasPrevious } = await getProductsPage(page);

  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

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
            <li key={p.slug}>
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
                <p>{p.is_small_pack && p.price_kes ? `From KES ${p.price_kes}` : "Request a quote"}</p>
              </Link>
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
