// Single source of business identity for the frontend. Every domain, phone,
// address, brand string and delivery claim used anywhere in app/ or
// components/ must come from here — and this file reads only from runtime
// server-side env vars (never NEXT_PUBLIC_*, never inlined at build time).
// Values are only ever needed in server components / route handlers, so
// plain `process.env` is correct: it's read fresh on each server execution,
// not baked into the client bundle.

function env(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

// These fallbacks are load-bearing for SEO: `url` seeds metadataBase, every
// canonical, the sitemap and all JSON-LD @ids. It previously defaulted to
// karivex.co.ke, a domain that was never registered (NXDOMAIN at the .ke
// registry) — so any deploy that lost SITE_URL would have silently pointed
// the entire site's canonicals at a host that does not exist, deindexing it.
// Fallbacks now match the live deployment.
export const site = {
  url: env("SITE_URL", "https://karivexsolutionsltd.com"),
  // The apex brand domain. Currently identical to `url` — the apex is the
  // canonical host — but kept as its own field because the two answer
  // different questions: `url` is "which host serves these pages" (canonicals,
  // sitemap, metadataBase), `brandUrl` is "which domain IS this company"
  // (the Organization node's official website in lib/schema.ts). They were
  // different before the site moved off industrialchemicals.*, and would
  // diverge again if the catalogue ever moved to its own host; whenever they
  // differ, lib/schema.ts ties both to one entity via sameAs.
  brandUrl: env("SITE_BRAND_URL", "https://karivexsolutionsltd.com"),
  name: env("SITE_NAME", "Karivex Solutions Ltd"),
  shortName: env("SITE_SHORT_NAME", "Karivex"),
  tagline: env("SITE_TAGLINE", "Chemical Division"),
  legalName: env("SITE_LEGAL_NAME", "Karivex Solutions Ltd"),
  // Every string a person or a model might use for this company. Feeds
  // schema.org `alternateName`, which is how a query for "Karivex" resolves to
  // the entity whose registered name is "Karivex Solutions Ltd".
  alternateNames: env("SITE_ALTERNATE_NAMES", "Karivex,Karivex Solutions,Karivex Chemicals")
    .split(",")
    .map((n) => n.trim())
    .filter(Boolean),
  // One-sentence statement of what the company is. Leads with the full legal
  // name on purpose: this string is reused verbatim in JSON-LD, the meta
  // description and the homepage intro, so the name/identity pairing is
  // repeated consistently everywhere an extractor looks.
  description: env(
    "SITE_DESCRIPTION",
    "Karivex Solutions Ltd is a trusted, leading supplier of chemicals — bulk distribution, supply chain management and procurement services for the industrial chemicals sector in Kenya.",
  ),
  // Authoritative third-party profiles (LinkedIn, Google Business Profile,
  // company registry, trade directories). Empty until they exist — an
  // Organization with no `sameAs` is the single biggest reason a real company
  // fails to resolve as an entity, so populating this is high priority.
  sameAs: env("SITE_SAME_AS", "")
    .split(",")
    .map((u) => u.trim())
    .filter(Boolean),
  phone: env("SITE_PHONE", "+254700000000"),
  // Second sales line. Both numbers reach the same team, so they are labelled
  // as one role rather than invented into "sales" and "support" — a label the
  // site cannot honour is worse than no label, because a buyer routed by it
  // reaches the wrong person and blames the supplier.
  //
  // Empty by default: every phone surface reads `phones` below, so an
  // unconfigured deployment renders exactly one number with no empty markup.
  phoneAlt: env("SITE_PHONE_ALT", ""),
  whatsapp: env("SITE_WHATSAPP", "+254700000000"),
  email: env("SITE_EMAIL", "info@karivexsolutionsltd.com"),
  address: {
    street: env("SITE_ADDRESS_STREET", "Enterprise Road, Industrial Area"),
    locality: env("SITE_ADDRESS_LOCALITY", "Nairobi"),
    region: env("SITE_ADDRESS_REGION", "Nairobi County"),
    // 00400, not 00100. The deployment has always sent 00400 via .env; this
    // fallback was left on the generic Nairobi GPO code when the others were
    // corrected to match the live values. It matters beyond tidiness: the
    // postcode is part of the NAP string every directory citation has to agree
    // on character-for-character, so a deploy that lost this variable would
    // start publishing an address that contradicts every listing built against
    // docs/seo-citations.md — and inconsistent NAP is precisely what stops
    // citations resolving to one entity.
    postalCode: env("SITE_ADDRESS_POSTAL_CODE", "00400"),
    country: env("SITE_ADDRESS_COUNTRY", "KE"),
  },
  regions: env("SITE_REGIONS", "Kenya,Uganda,Tanzania,Rwanda")
    .split(",")
    .map((r) => r.trim())
    .filter(Boolean),
  hours: env("SITE_HOURS", "Mo-Fr 08:00-17:00, Sa 08:00-13:00"),
  deliveryNairobi: env("SITE_DELIVERY_NAIROBI", "24-hour delivery in Nairobi"),
  deliveryRegional: env("SITE_DELIVERY_REGIONAL", "2-3 day delivery to Uganda, Tanzania & Rwanda"),
  certifications: env("SITE_CERTIFICATIONS", "COA & MSDS with every order"),
} as const;

export const SITE_URL = site.url;

export interface PhoneLine {
  /** E.164, used for `tel:` hrefs and schema.org `telephone`. */
  number: string;
  /** Short role shown beside the number on lookup surfaces. */
  label: string;
  /** True for the one number used by single-action CTAs. */
  primary: boolean;
}

/**
 * Every voice line the company publishes, primary first.
 *
 * One list behind all of it so a third number is a config change, not another
 * sweep through thirteen components — which is how the site ended up with the
 * phone number hard-wired into hero copy, product buttons and JSON-LD
 * separately in the first place.
 *
 * Deliberately NOT used by the single-action call-to-action surfaces (the
 * product "Call" button, the hero and category CTAs, the floating contact
 * rail). Those render `site.phone` alone: a CTA offering two numbers asks the
 * buyer to make a decision before they can act, and the whole purpose of that
 * button is that a buyer arriving from a phone search result can tap once.
 * Lookup surfaces — the top bar, the footer, /contact — are where a second
 * number earns its place, because someone reading those is choosing who to
 * call, not being asked to.
 */
export const phones: PhoneLine[] = [
  { number: site.phone, label: "Sales", primary: true },
  ...(site.phoneAlt
    ? [{ number: site.phoneAlt, label: "Sales (alt)", primary: false }]
    : []),
];

/** Digits only, for `wa.me/` and `tel:` where formatting must not leak in. */
export function dialable(number: string): string {
  return number.replace(/[^\d+]/g, "");
}

/**
 * Kenyan numbers grouped the way they are read aloud: +254 742 355548.
 * Display only — never use this for a `tel:` href or for schema.
 */
export function formatPhone(number: string): string {
  const m = dialable(number).match(/^\+254(\d{3})(\d{6})$/);
  return m ? `+254 ${m[1]} ${m[2]}` : number;
}

/**
 * Lower-cases a config string for use mid-sentence — but only its first
 * character, and only when the opening word is not an acronym.
 *
 * These values are authored in sentence case ("COA & MSDS with every order",
 * "24-hour delivery in Nairobi") because they are also rendered as standalone
 * headings. Splicing them into running prose previously used `.toLowerCase()`,
 * which flattened every proper noun and initialism in the string: the homepage
 * shipped "coa & msds", "delivery in nairobi" and "uganda, tanzania & rwanda"
 * to production. Lower-casing only the first character fixes that, and the
 * all-caps guard leaves acronym-initial strings alone entirely — "COA" must
 * not become "cOA".
 */
export function decap(s: string): string {
  const [first = ""] = s.split(" ");
  // Acronym-initial (COA, MSDS, ISO…) — any change would be wrong.
  if (first.length > 1 && first === first.toUpperCase() && /[A-Z]/.test(first)) return s;
  return s.charAt(0).toLowerCase() + s.slice(1);
}

/**
 * Clamps a meta description to `max` characters without cutting a word in half.
 *
 * `.slice(0, 160)` is what this replaces, and it was visibly wrong in the
 * SERP: 18 category pages ended on a hard 160-byte cut mid-word — "…COA & MSDS
 * with every order. 24-hour delivery in Nai" — because the composed string ran
 * a few characters past the limit. Google renders the truncated text as-is, so
 * a snippet that stops mid-word is what a searcher actually reads.
 *
 * Trailing separators are dropped before the ellipsis so the result never
 * reads "… in Nairobi, …". The ellipsis is a single character, counted inside
 * the budget rather than appended past it.
 */
export function clampDescription(s: string, max = 160): string {
  const text = s.replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1);
  // Prefer ending on a completed sentence when one is available late enough to
  // still be a useful description; otherwise fall back to the last whole word.
  const sentence = cut.lastIndexOf(". ");
  if (sentence >= max * 0.6) return cut.slice(0, sentence + 1);
  const word = cut.lastIndexOf(" ");
  return (word > 0 ? cut.slice(0, word) : cut).replace(/[\s,;:·—-]+$/, "") + "…";
}
