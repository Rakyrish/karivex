import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getProduct, getProducts, SITE_URL } from "@/lib/api";
import QuoteForm from "@/components/QuoteForm";
import BuyButton from "@/components/BuyButton";

// ISR: pages are static, purged by Django post_save -> /api/revalidate.
// No time-based revalidate needed; the webhook is the source of truth.
export const dynamicParams = true;

export async function generateStaticParams() {
  const products = await getProducts();
  return products.map((p) => ({ slug: p.slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) return {};
  return {
    title: product.meta_title,
    description:
      product.meta_description ||
      `${product.name} (${product.purity}) supplied across ${product.regions}. ${product.packaging}. COA & MSDS included. Request a quote or order online from Karivex Solutions, Nairobi.`.slice(0, 160),
    alternates: { canonical: `${SITE_URL}/products/${slug}` },
    openGraph: {
      title: product.meta_title,
      type: "website",
      url: `${SITE_URL}/products/${slug}`,
      images: product.image
        ? [{ url: product.image, alt: product.image_alt }]
        : [{ url: `${SITE_URL}/og?type=product&title=${encodeURIComponent(product.name)}`, width: 1200, height: 630 }],
    },
  };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();

  const url = `${SITE_URL}/products/${product.slug}`;

  // --- Structured data. This is the moat: none of the four competitors emit
  // Product, FAQPage, or BreadcrumbList schema. Rich results = higher CTR.
  // Each PropertyValue is independent — a product missing a CAS number (e.g.
  // a blend/mixture) must not also lose its purity/grade/packaging schema,
  // which an earlier version of this file did by nesting all four behind a
  // single `cas_number &&` gate.
  const additionalProperty = [
    product.cas_number && { "@type": "PropertyValue", name: "CAS Number", value: product.cas_number },
    product.purity && { "@type": "PropertyValue", name: "Purity", value: product.purity },
    product.grade && { "@type": "PropertyValue", name: "Grade", value: product.grade },
    product.packaging && { "@type": "PropertyValue", name: "Packaging", value: product.packaging },
  ].filter(Boolean);

  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.meta_description || product.description.slice(0, 300),
    sku: product.slug,
    ...(additionalProperty.length > 0 && { additionalProperty }),
    ...(product.image && { image: product.image }),
    brand: { "@type": "Brand", name: "Karivex Solutions Ltd" },
    offers: {
      "@type": "Offer",
      url,
      priceCurrency: "KES",
      // Quote-only products: omit price, keep availability. Google accepts this.
      ...(product.is_small_pack && product.price_kes
        ? { price: product.price_kes }
        : {}),
      availability: product.in_stock
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
      areaServed: product.regions.split(",").map((r: string) => r.trim()),
      seller: { "@type": "Organization", name: "Karivex Solutions Ltd" },
    },
  };

  const faqSchema =
    product.faqs?.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: product.faqs.map((f: { q: string; a: string }) => ({
            "@type": "Question",
            name: f.q,
            acceptedAnswer: { "@type": "Answer", text: f.a },
          })),
        }
      : null;

  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: product.category.name, item: `${SITE_URL}/categories/${product.category.slug}` },
      { "@type": "ListItem", position: 3, name: product.name, item: url },
    ],
  };

  return (
    <article className="product-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(productSchema) }} />
      {faqSchema && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }} />
      )}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> /{" "}
        <Link href={`/categories/${product.category.slug}`}>{product.category.name}</Link> /{" "}
        <span aria-current="page">{product.name}</span>
      </nav>

      <header>
        <h1>
          {product.name} — Supplier in Kenya &amp; East Africa
        </h1>
        <p className="lede">
          {product.purity && <>Purity {product.purity} · </>}
          {product.packaging} · Delivered across {product.regions}
        </p>
      </header>

      <section aria-labelledby="specs">
        <h2 id="specs">Specifications</h2>
        <table>
          <tbody>
            {product.cas_number && <tr><th scope="row">CAS Number</th><td>{product.cas_number}</td></tr>}
            {product.synonyms && <tr><th scope="row">Synonyms</th><td>{product.synonyms}</td></tr>}
            <tr><th scope="row">Grade</th><td>{product.grade}</td></tr>
            {product.purity && <tr><th scope="row">Purity</th><td>{product.purity}</td></tr>}
            {product.appearance && <tr><th scope="row">Appearance</th><td>{product.appearance}</td></tr>}
            {product.packaging && <tr><th scope="row">Packaging</th><td>{product.packaging}</td></tr>}
            <tr><th scope="row">Availability</th><td>{product.in_stock ? "In stock — Nairobi warehouse" : "On order"}</td></tr>
          </tbody>
        </table>
      </section>

      <section aria-labelledby="about">
        <h2 id="about">About {product.name}</h2>
        {product.description.split("\n\n").map((para: string, i: number) => (
          <p key={i}>{para}</p>
        ))}
      </section>

      {product.applications && (
        <section aria-labelledby="apps">
          <h2 id="apps">Applications</h2>
          <ul>
            {product.applications.split("\n").filter(Boolean).map((a: string, i: number) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </section>
      )}

      {product.safety_info && (
        <section aria-labelledby="safety">
          <h2 id="safety">Handling &amp; Safety</h2>
          <p>{product.safety_info}</p>
          <p>MSDS and COA are supplied with every order.</p>
        </section>
      )}

      {product.faqs?.length > 0 && (
        <section aria-labelledby="faq">
          <h2 id="faq">Frequently asked questions</h2>
          {product.faqs.map((f: { q: string; a: string }, i: number) => (
            <details key={i}>
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </section>
      )}

      <section aria-labelledby="order" className="order-panel">
        <h2 id="order">Order {product.name}</h2>
        {product.is_small_pack && product.price_kes ? (
          <BuyButton product={product} />
        ) : null}
        <QuoteForm productId={product.id} productName={product.name} />
      </section>
    </article>
  );
}
