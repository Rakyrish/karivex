import type { Metadata } from "next";
import Link from "next/link";
import { getProduct, SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";
import { ORG_ID, jsonLd } from "@/lib/schema";
import QuoteForm from "@/components/QuoteForm";

export const metadata: Metadata = {
  title: `Request a Quote | ${site.shortName}`,
  description: `Request a bulk quote or place a small-pack order from ${site.name}. We reply within one business hour, Mon–Sat.`,
  alternates: { canonical: `${SITE_URL}/quote` },
};

type Props = { searchParams: Promise<{ product?: string; mode?: string }> };

export default async function QuotePage({ searchParams }: Props) {
  const { product: productSlug, mode: modeParam } = await searchParams;
  const mode = modeParam === "buy" ? "buy" : "quote";
  const product = productSlug ? await getProduct(productSlug) : null;

  // The only indexable page on the site that carried no page-level structured
  // data — every other one already ships a BreadcrumbList. Nodes are pinned to
  // the bare /quote URL, never to the ?product= / ?mode= variant being
  // rendered, so the parameterised entry points that CTAs link to all resolve
  // to the single node the static canonical above already consolidates them
  // onto. Emitting the variant URL here would re-split what that canonical
  // just merged.
  const canonical = `${SITE_URL}/quote`;
  const quoteGraph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebPage",
        "@id": canonical,
        url: canonical,
        name: "Request a quote",
        description: `Request a bulk quote or place a small-pack order from ${site.name}.`,
        inLanguage: "en-KE",
        isPartOf: { "@id": `${SITE_URL}/#website` },
        breadcrumb: { "@id": `${canonical}#breadcrumb` },
        publisher: { "@id": ORG_ID },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonical}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Request a quote", item: canonical },
        ],
      },
    ],
  };

  return (
    <section className="quote-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(quoteGraph) }} />
      <h1>{mode === "buy" ? "Order online" : "Request a quote"}</h1>
      <p className="lede">
        {product ? (
          <>
            For <Link href={`/products/${product.slug}`}>{product.name}</Link>. Not the right product?{" "}
            <Link href="/quote">Start a general inquiry</Link> instead.
          </>
        ) : (
          <>
            Tell us what you need and we&rsquo;ll get back to you within one business hour
            (Mon&ndash;Sat, EAT). Bulk orders across {site.regions.join(", ")} welcome.
          </>
        )}
      </p>
      <QuoteForm
        productId={product?.id}
        productName={product?.name}
        mode={mode}
      />
    </section>
  );
}
