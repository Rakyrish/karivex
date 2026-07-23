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
  return {
    title: cat.meta_title,
    description: cat.meta_description || cat.description?.slice(0, 160),
    alternates: { canonical: `${SITE_URL}/categories/${slug}` },
  };
}

export default async function CategoryPage({ params }: Props) {
  const { slug } = await params;
  const cat = await getCategory(slug);
  if (!cat) notFound();
  const products = await getProductsByCategory(slug);

  const itemList = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    itemListElement: products.map((p, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: `${SITE_URL}/products/${p.slug}`,
    })),
  };

  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(itemList) }} />
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
    </section>
  );
}
