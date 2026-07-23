import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${site.name} — Industrial Chemical Suppliers in Kenya & East Africa`,
    template: "%s",
  },
  description: `${site.name} supplies industrial, food-grade and lab chemicals across ${site.regions.join(", ")}. ${site.certifications}. ${site.deliveryNairobi}.`,
  openGraph: {
    type: "website",
    siteName: site.name,
    images: [{ url: `${SITE_URL}/og?title=${encodeURIComponent(site.name)}`, width: 1200, height: 630 }],
  },
};

// LocalBusiness schema — none of the competitors emit this. Pairs with a
// Google Business Profile for the local pack ("chemical supplier near me").
const localBusiness = {
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "@id": `${SITE_URL}/#org`,
  name: `${site.name} — ${site.tagline}`,
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
  areaServed: site.regions,
  openingHours: site.hours,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(localBusiness) }}
        />
        <header className="site-header">
          <Link href="/" className="brand">{site.shortName.toUpperCase()}<span>{site.tagline.toLowerCase()}</span></Link>
          <nav>
            <Link href="/#categories">Products</Link>
            <Link href="/blog">Guides</Link>
            <Link href="/quote">Request a quote</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <p>{site.name} — {site.tagline} · {site.address.locality}, {site.address.country === "KE" ? "Kenya" : site.address.country}</p>
          <p>Serving {site.regions.join(", ")} · {site.certifications}</p>
          <p>
            <a href={`tel:${site.phone}`}>{site.phone}</a> ·{" "}
            <a href={`mailto:${site.email}`}>{site.email}</a>
          </p>
        </footer>
      </body>
    </html>
  );
}
