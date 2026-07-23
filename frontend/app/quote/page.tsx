import type { Metadata } from "next";
import Link from "next/link";
import { getProduct, SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";
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

  return (
    <section className="quote-page">
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
