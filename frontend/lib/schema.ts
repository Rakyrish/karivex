// Single source of the site's structured-data identity graph.
//
// Why this file exists: the schema was previously split across two components
// that each declared a node with the SAME @id (`<url>/#org`) but a different
// @type and a different `name` — layout.tsx emitted LocalBusiness named
// "Karivex Solutions Ltd — Chemical Division", page.tsx emitted Organization
// named "Karivex Solutions Ltd". Consumers merge nodes by @id, so the company
// arrived at Google as one contradictory blob with two names and two types,
// and the Organization half only existed on the homepage. One graph, emitted
// once from the root layout, removes the contradiction.
//
// On @type: schema.org has no `ChemicalBusiness` type (https://schema.org/
// ChemicalBusiness is a 404). Emitting it would leave the node effectively
// untyped, which is strictly worse than being generic. The valid way to say
// "a company with a physical trading location" is the pair below —
// LocalBusiness is a subclass of Organization, so the node satisfies both the
// entity-resolution path (Organization) and the local/physical path
// (LocalBusiness) with no invented vocabulary. The chemical specialisation is
// carried by `knowsAbout` + `description` instead.

import { site, phones, SITE_URL } from "./site";

// Stable, absolute, brand-domain-scoped identifier. It never changes even if
// the catalogue moves host, which is what lets Google keep treating this as
// the same entity across the move.
export const ORG_ID = `${site.brandUrl}/#organization`;
const LOGO_ID = `${site.brandUrl}/#logo`;
const WEBSITE_ID = `${SITE_URL}/#website`;

// The catalogue host and the brand host are the same company. Declaring the
// other host in `sameAs` is what stops them being read as two unrelated sites.
const sameAs = Array.from(
  new Set([...(site.brandUrl === SITE_URL ? [] : [SITE_URL]), ...site.sameAs]),
);

const postalAddress = {
  "@type": "PostalAddress",
  streetAddress: site.address.street,
  addressLocality: site.address.locality,
  addressRegion: site.address.region,
  postalCode: site.address.postalCode,
  addressCountry: site.address.country,
};

const organization = {
  "@type": ["Organization", "LocalBusiness"],
  "@id": ORG_ID,
  name: site.legalName,
  legalName: site.legalName,
  alternateName: site.alternateNames,
  description: site.description,
  url: site.brandUrl,
  // Square PNG rather than the 1254px source JPEG: Google's Organization logo
  // guidance wants a clean square raster, and this is a quarter of the bytes.
  logo: {
    "@type": "ImageObject",
    "@id": LOGO_ID,
    url: `${SITE_URL}/brand/logo-512.png`,
    contentUrl: `${SITE_URL}/brand/logo-512.png`,
    width: 512,
    height: 512,
    caption: site.legalName,
  },
  image: { "@id": LOGO_ID },
  // Every published line, not just the first. schema.org allows repeated
  // `telephone` values, and a number that appears on the page but not here is
  // a number Google cannot attach to the entity — which is what powers the
  // "Call" button on a Business Profile and the knowledge panel.
  telephone: phones.map((p) => p.number),
  email: site.email,
  address: postalAddress,
  // `location` restates the address as a Place. Without it the business has an
  // address but no physical entity — the specific gap that makes a real
  // company read as a name with no premises behind it.
  location: {
    "@type": "Place",
    "@id": `${site.brandUrl}/#warehouse`,
    name: `${site.legalName} — ${site.address.locality} warehouse`,
    address: postalAddress,
  },
  areaServed: site.regions.map((r) => ({ "@type": "Country", name: r })),
  openingHours: site.hours,
  // One ContactPoint per line. Both carry contactType "sales" because both
  // reach the same desk — splitting them into "sales" and "customer support"
  // would be a claim about internal routing the company has not made.
  contactPoint: phones.map((p) => ({
    "@type": "ContactPoint",
    contactType: "sales",
    telephone: p.number,
    email: site.email,
    areaServed: site.regions,
    availableLanguage: ["en", "sw"],
    hoursAvailable: site.hours,
  })),
  // The topical claim that a generic Organization node cannot make. This is
  // what ties the entity to "industrial chemicals in Kenya" rather than
  // leaving it as an unqualified company name.
  knowsAbout: [
    "Industrial chemicals",
    "Bulk chemical distribution",
    "Chemical procurement",
    "Chemical supply chain management",
    "Water treatment chemicals",
    "Food-grade chemicals",
    "Laboratory reagents",
  ],
  ...(sameAs.length > 0 ? { sameAs } : {}),
};

const website = {
  "@type": "WebSite",
  "@id": WEBSITE_ID,
  url: SITE_URL,
  name: `${site.legalName} — ${site.tagline}`,
  description: site.description,
  inLanguage: "en-KE",
  publisher: { "@id": ORG_ID },
  // Declares the catalogue search at /search?q=. Worth being straight about
  // what this does and does not buy: Google retired the sitelinks searchbox
  // rich result in November 2024, so this will not render one. It is here
  // because it is a true, machine-readable statement that the site has a
  // searchable catalogue and how to query it — which is what an agent or a
  // non-Google extractor needs to use the catalogue directly instead of
  // crawling all 182 product pages to find one chemical. The target is a real,
  // working route (app/search/page.tsx reads `q`), not an aspirational one.
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${SITE_URL}/search?q={search_term_string}`,
    },
    "query-input": "required name=search_term_string",
  },
};

export const identityGraph = {
  "@context": "https://schema.org",
  "@graph": [organization, website],
};

// JSON-LD goes into the page via dangerouslySetInnerHTML, so any "</script>"
// (or "<!--") that ever reached a config value would break out of the script
// element. Escaping every "<" to its unicode form is inert to JSON parsers
// and closes that hole for good.
export function jsonLd(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
