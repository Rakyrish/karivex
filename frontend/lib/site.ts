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

export const site = {
  url: env("SITE_URL", "https://karivex.co.ke"),
  name: env("SITE_NAME", "Karivex Solutions Ltd"),
  shortName: env("SITE_SHORT_NAME", "Karivex"),
  tagline: env("SITE_TAGLINE", "Chemical Division"),
  legalName: env("SITE_LEGAL_NAME", "Karivex Solutions Ltd"),
  phone: env("SITE_PHONE", "+254700000000"),
  whatsapp: env("SITE_WHATSAPP", "+254700000000"),
  email: env("SITE_EMAIL", "sales@karivex.co.ke"),
  address: {
    street: env("SITE_ADDRESS_STREET", "Enterprise Road, Industrial Area"),
    locality: env("SITE_ADDRESS_LOCALITY", "Nairobi"),
    region: env("SITE_ADDRESS_REGION", "Nairobi County"),
    postalCode: env("SITE_ADDRESS_POSTAL_CODE", "00100"),
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
