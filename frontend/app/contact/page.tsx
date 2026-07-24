import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";
import QuoteForm from "@/components/QuoteForm";

export const metadata: Metadata = {
  title: `Contact ${site.shortName} | ${site.address.locality}, ${site.address.country === "KE" ? "Kenya" : site.address.country}`,
  description: `Call, WhatsApp or email ${site.name} directly, or send a general inquiry. We reply within one business hour, ${site.hours}.`,
  alternates: { canonical: `${SITE_URL}/contact` },
  openGraph: {
    title: `Contact ${site.shortName}`,
    type: "website",
    url: `${SITE_URL}/contact`,
    images: [{ url: `${SITE_URL}/og?type=contact&title=${encodeURIComponent(`Contact ${site.shortName}`)}`, width: 1200, height: 630 }],
  },
};

const breadcrumbSchema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
    { "@type": "ListItem", position: 2, name: "Contact", item: `${SITE_URL}/contact` },
  ],
};

const contactPageSchema = {
  "@context": "https://schema.org",
  "@type": "ContactPage",
  url: `${SITE_URL}/contact`,
  mainEntity: {
    "@type": "Organization",
    name: site.name,
    url: SITE_URL,
    telephone: site.phone,
    email: site.email,
    address: {
      "@type": "PostalAddress",
      streetAddress: site.address.street,
      addressLocality: site.address.locality,
      addressRegion: site.address.region,
      postalCode: site.address.postalCode,
      addressCountry: site.address.country,
    },
  },
};

export default function ContactPage() {
  return (
    <section className="contact-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(contactPageSchema) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <span aria-current="page">Contact</span>
      </nav>

      <h1>Contact {site.shortName}</h1>
      <p className="lede">
        Call, WhatsApp or email us directly, or send a message below — we reply within one business hour,{" "}
        {site.hours}.
      </p>

      <div className="contact-grid">
        <div>
          <h2>Reach us directly</h2>
          <div className="contact-info">
            <div className="contact-info-card">
              <h3>Phone</h3>
              <p><a href={`tel:${site.phone}`}>{site.phone}</a></p>
            </div>
            <div className="contact-info-card">
              <h3>WhatsApp</h3>
              <p><a href={`https://wa.me/${site.whatsapp.replace(/[^\d]/g, "")}`}>Message us on WhatsApp</a></p>
            </div>
            <div className="contact-info-card">
              <h3>Email</h3>
              <p><a href={`mailto:${site.email}`}>{site.email}</a></p>
            </div>
            <div className="contact-info-card">
              <h3>Warehouse address</h3>
              <p>
                {site.address.street}<br />
                {site.address.locality}, {site.address.region}{" "}
                {site.address.postalCode}<br />
                {site.address.country === "KE" ? "Kenya" : site.address.country}
              </p>
            </div>
            <div className="contact-info-card">
              <h3>Hours</h3>
              <p>{site.hours}</p>
            </div>
            <div className="contact-info-card">
              <h3>Regions served</h3>
              <p>{site.regions.join(", ")}</p>
            </div>
          </div>
        </div>

        <div>
          <h2>Send us a message</h2>
          <QuoteForm mode="contact" />
        </div>
      </div>

      <p className="lede">
        Looking for a specific product quote instead? <Link href="/quote">Use the quote form</Link> so we can
        price it against a real specification.
      </p>
    </section>
  );
}
