import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { Alice, Inter } from "next/font/google";
import "./globals.css";
import { SITE_URL, getCategories } from "@/lib/api";
import { site } from "@/lib/site";
import CategoryNav from "@/components/CategoryNav";
import ChatWidget from "@/components/ChatWidget";
import TopBar from "@/components/TopBar";
import Footer from "@/components/Footer";
import MobileNav from "@/components/MobileNav";

const NAV_LINKS = [
  { href: "/products", label: "Products" },
  { href: "/about", label: "About" },
  { href: "/blog", label: "Guides" },
  { href: "/contact", label: "Contact" },
];

const heading = Alice({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-heading",
  display: "swap",
});
const body = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

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

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const categories = await getCategories();

  return (
    <html lang="en" className={`${heading.variable} ${body.variable}`}>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(localBusiness) }}
        />
        <TopBar phone={site.phone} email={site.email} whatsapp={site.whatsapp} hours={site.hours} regions={site.regions} />
        <header className="site-header">
          <div className="site-header-inner">
            <Link href="/" className="brand">
              <span className="brand-mark">
                <Image src="/brand/logo.jpg" alt={`${site.name} logo`} width={48} height={48} priority />
              </span>
              <span className="brand-word">
                <strong className="brand-name-full">{site.name}</strong>
                <strong className="brand-name-short">{site.shortName}</strong>
                <span>{site.tagline.toLowerCase()}</span>
              </span>
            </Link>
            <nav>
              <MobileNav links={NAV_LINKS} quoteHref="/quote" quoteLabel="Request a quote" />
              {NAV_LINKS.map((l) => (
                <Link key={l.href} href={l.href} className="nav-link-desktop">{l.label}</Link>
              ))}
              <a href={`tel:${site.phone}`} className="nav-phone" aria-label={`Call ${site.phone}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
                <span>{site.phone}</span>
              </a>
              <Link href="/quote" className="nav-cta nav-link-desktop">Request a quote</Link>
            </nav>
          </div>
        </header>
        <CategoryNav categories={categories} />
        <main>{children}</main>
        <Footer site={site} categories={categories} />
        <ChatWidget phone={site.phone} whatsapp={site.whatsapp} />
      </body>
    </html>
  );
}
