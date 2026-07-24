import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: `About ${site.name} | Industrial Chemical Supplier in Kenya & East Africa`,
  description: `${site.name} supplies industrial, food-grade, laboratory, pharmaceutical and cosmetic-grade chemicals from ${site.address.locality}, delivered across ${site.regions.join(", ")} with ${site.certifications.toLowerCase()}.`,
  alternates: { canonical: `${SITE_URL}/about` },
  openGraph: {
    title: `About ${site.name}`,
    type: "website",
    url: `${SITE_URL}/about`,
    images: [{ url: `${SITE_URL}/og?type=about&title=${encodeURIComponent(`About ${site.name}`)}`, width: 1200, height: 630 }],
  },
};

const breadcrumbSchema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
    { "@type": "ListItem", position: 2, name: "About", item: `${SITE_URL}/about` },
  ],
};

export default function AboutPage() {
  return (
    <section className="about-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <span aria-current="page">About</span>
      </nav>

      <h1>About {site.name}</h1>
      <p className="lede">
        {site.name} is the {site.tagline.toLowerCase()} supplying industrial, food-grade, laboratory,
        pharmaceutical and cosmetic-grade chemicals from a single {site.address.locality} warehouse, delivered
        across {site.regions.join(", ")}.
      </p>

      <div className="about-grid">
        <section aria-labelledby="what-we-supply" className="about-card">
          <h2 id="what-we-supply">What we supply</h2>
          <p>
            Our catalogue spans bulk process chemicals through to small retail packs, organised by category
            rather than by manufacturer — so a buyer looking for water treatment chemicals, solvents, or
            construction additives can compare specifications directly. Every product carries its own purity,
            packaging and CAS reference rather than a shared manufacturer data sheet copied across similar
            products.
          </p>
          <p className="about-card-links">
            <Link href="/products">Browse the full catalogue</Link> or{" "}
            <Link href="/quote">request a quote</Link> for a specification we haven&rsquo;t listed yet.
          </p>
        </section>

        <section aria-labelledby="how-we-operate" className="about-card">
          <h2 id="how-we-operate">How we operate</h2>
          <p>
            Bulk and small-pack orders both move through the same {site.address.locality} warehouse and the
            same quote process, answered within one business hour, {site.hours}. {site.deliveryNairobi},{" "}
            {site.deliveryRegional.toLowerCase()} — the same lead times whether the order is a single drum or
            a full truckload.
          </p>
        </section>

        <section aria-labelledby="compliance-commitment" className="about-card">
          <h2 id="compliance-commitment">Our compliance commitment</h2>
          <p>
            {site.certifications} — not as a paid add-on, but as the default for every order. We treat batch
            documentation as part of the product, not paperwork bolted on afterwards, because a chemical
            without traceable specifications is a liability for whoever receives it next in the supply chain.
          </p>
        </section>
      </div>

      <section aria-labelledby="get-in-touch" className="about-cta">
        <h2 id="get-in-touch">Get in touch</h2>
        <p>
          Reach our {site.address.locality} team directly at{" "}
          <a href={`tel:${site.phone}`}>{site.phone}</a> or <a href={`mailto:${site.email}`}>{site.email}</a>,
          or see full contact details on the <Link href="/contact">contact page</Link>.
        </p>
        <div className="hero-actions">
          <Link href="/quote" className="cta">Request a quote</Link>
          <Link href="/contact" className="cta-ghost">Contact us</Link>
        </div>
      </section>
    </section>
  );
}
