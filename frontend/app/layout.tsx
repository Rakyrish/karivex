import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { Alice, Inter } from "next/font/google";
import "./globals.css";
import { SITE_URL, getCategories, getProducts } from "@/lib/api";
import { site, phones } from "@/lib/site";
import { identityGraph, jsonLd } from "@/lib/schema";
import MegaMenu from "@/components/MegaMenu";
import ChatWidget from "@/components/ChatWidget";
import ContactRail from "@/components/ContactRail";
import TopBar from "@/components/TopBar";
import Footer from "@/components/Footer";
import MobileNav from "@/components/MobileNav";
import SearchBox from "@/components/SearchBox";

const NAV_LINKS = [
  { href: "/products", label: "Products" },
  { href: "/how-we-work", label: "How we work" },
  { href: "/about", label: "About" },
  { href: "/blog", label: "Guides" },
  { href: "/contact", label: "Contact" },
];

// Shown inline on the mega-menu bar, beside the industry trigger.
const CATALOGUE_LINKS = [
  { href: "/products", label: "All products" },
  // Sitewide entry point to the category hub — without it /categories would
  // itself be an orphan, and the hub only earns its keep if crawlers reach it.
  { href: "/categories", label: "All categories" },
  { href: "/products?featured=true", label: "Featured" },
  { href: "/blog", label: "Buying guides" },
  { href: "/quote", label: "Request a quote" },
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
    // The legal name leads, and the city is named: "Karivex Solutions Ltd" and
    // "Nairobi" now co-occur in the one string every SERP and every extractor
    // reads first.
    default: `${site.legalName} | Industrial Chemical Suppliers Kenya`,
    template: "%s",
  },
  description: `${site.legalName} is an industrial chemical distributor in Nairobi, Kenya. Bulk supply and procurement across East Africa. ${site.certifications}.`,
  applicationName: site.legalName,
  authors: [{ name: site.legalName, url: site.brandUrl }],
  publisher: site.legalName,
  keywords: [
    site.legalName,
    site.shortName,
    "industrial chemical supplier Nairobi",
    "chemical distributor Kenya",
    "bulk chemical supply Kenya",
    "chemical procurement Kenya",
  ],
  openGraph: {
    type: "website",
    siteName: site.legalName,
    locale: "en_KE",
    images: [{ url: `${SITE_URL}/og?title=${encodeURIComponent(site.legalName)}`, width: 1200, height: 630 }],
  },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Both lists are already static at build time; the search index is the
  // same product list the catalogue pages use, so this adds no extra round
  // trip and the header search works without any client fetch.
  const [categories, products] = await Promise.all([getCategories(), getProducts()]);

  return (
    // en-KE, not bare "en": it pairs the document with the country the
    // Organization node claims to trade in.
    <html lang="en-KE" className={`${heading.variable} ${body.variable}`}>
      {/* Rendered into <head> rather than <body>. Both are valid to Google,
          but head-placed JSON-LD is what the stricter third-party extractors
          (and the crawlers behind AI answers) look at, and several never read
          past </head>. Next merges its Metadata API output into this same
          element, so nothing here conflicts with `metadata` above. */}
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLd(identityGraph) }}
        />
        {/* Ahrefs Web Analytics. Ahrefs documents two snippets — this tag, and
            a second one that builds the same tag with createElement. They are
            equivalent; the JS variant exists only for tag managers that cannot
            emit raw markup. Installing both would load analytics.js twice and
            double-count every pageview, so only this one is here.

            No `next/script` wrapper: React 19 already hoists and de-duplicates
            async scripts, and the plain tag keeps it in <head> where Ahrefs
            expects it, firing on first paint rather than after hydration. */}
        <script
          src="https://analytics.ahrefs.com/analytics.js"
          data-key="N5uUr+5BwkGuxqqaNWrpeQ"
          async
        />
      </head>
      <body>
        <TopBar phones={phones} email={site.email} whatsapp={site.whatsapp} hours={site.hours} regions={site.regions} />
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
            <SearchBox products={products} className="site-search-header" />
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
        <MegaMenu categories={categories} quickLinks={CATALOGUE_LINKS} />
        <main>{children}</main>
        <Footer site={site} categories={categories} />
        <ContactRail />
        <ChatWidget phone={site.phone} whatsapp={site.whatsapp} />
      </body>
    </html>
  );
}
