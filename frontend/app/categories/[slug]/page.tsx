import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getCategory, getCategories, getProductsByCategory, SITE_URL } from "@/lib/api";

export async function generateStaticParams() {
  const cats = await getCategories();
  return cats.map((c) => ({ slug: c.slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const cat = await getCategory(slug);
  if (!cat) return {};
  const url = `${SITE_URL}/categories/${slug}`;
  return {
    title: cat.meta_title,
    description: cat.meta_description || cat.description?.slice(0, 160),
    alternates: { canonical: url },
    openGraph: {
      title: cat.meta_title,
      type: "website",
      url,
      images: [{ url: `${SITE_URL}/og?type=category&title=${encodeURIComponent(cat.name)}`, width: 1200, height: 630 }],
    },
  };
}

export default async function CategoryPage({ params }: Props) {
  const { slug } = await params;
  const cat = await getCategory(slug);
  if (!cat) notFound();
  const [products, categories] = await Promise.all([
    getProductsByCategory(slug),
    getCategories(),
  ]);
  const otherCategories = categories.filter((c) => c.slug !== slug);
  const url = `${SITE_URL}/categories/${slug}`;

  const itemList = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    itemListElement: products.map((p, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: `${SITE_URL}/products/${p.slug}`,
    })),
  };

  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: cat.name, item: url },
    ],
  };

  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(itemList) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <span aria-current="page">{cat.name}</span>
      </nav>

      <h1>{cat.name} — Suppliers in Kenya &amp; East Africa</h1>
      {cat.description && <p className="lede">{cat.description}</p>}
      <ul className="product-grid">
        {products.map((p) => (
          <li key={p.slug}>
            <Link href={`/products/${p.slug}`}>
              <h2>{p.name}</h2>
              <p>{p.purity} · {p.packaging}</p>
              <p>{p.is_small_pack && p.price_kes ? `From KES ${p.price_kes}` : "Request a quote"}</p>
            </Link>
          </li>
        ))}
      </ul>

      {otherCategories.length > 0 && (
        <section aria-labelledby="other-categories" className="related-products">
          <h2 id="other-categories">Explore other categories</h2>
          <div className="category-nav-inner category-nav-inline">
            {otherCategories.map((c) => (
              <Link key={c.slug} href={`/categories/${c.slug}`} className="category-chip">
                {c.name}
              </Link>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
