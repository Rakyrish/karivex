// Reader for the structured product content produced by the backend
// `ai_tools` pipeline (see backend/ai_tools/content_schema.py — this mirrors
// that contract).
//
// Two jobs, both about not breaking what already works:
//
//  1. **Fallback.** Products generated before the structured pipeline existed
//     have empty `content_sections` and render from the flat
//     `description`/`applications`/`safety_info`/`faqs` columns. `readProduct`
//     resolves either shape into one view model, so the page component never
//     branches on which generation produced a product.
//
//  2. **Verification marker suppression.** The backend deliberately stores
//     "Requires manual verification" wherever a value could not be confirmed.
//     That marker is for staff. A buyer must never see it, and a spec row
//     carrying it must not reach JSON-LD either — publishing a placeholder as
//     a product attribute is worse than omitting the attribute.

export const NEEDS_VERIFICATION = "Requires manual verification";

export interface SpecRow {
  label: string;
  value: string;
  verified?: boolean;
}

export interface ContentSections {
  summary?: string;
  key_features?: string[];
  benefits?: Array<{ title: string; detail: string }>;
  specifications?: SpecRow[];
  available_grades?: string[];
  grades_note?: string;
  packaging_options?: string[];
  /** Pairs since the applications section was re-typed. Products generated
   *  before that still hold plain strings; `readApplications` resolves both. */
  applications?: Array<{ use?: string; why?: string }> | string[];
  industries?: Array<{ name: string; detail: string }>;
  typical_uses?: Array<{ scenario: string; guidance: string }>;
  why_choose_us?: string[];
  delivery_coverage?: { regions?: string[]; notes?: string[] };
  storage_guidelines?: string;
  handling_safety?: {
    guidance?: string;
    ppe?: string[];
    /** Transcribed from the supplier SDS by staff, never generated. Absent
     *  until someone has the document in hand — which is the correct state. */
    first_aid?: string;
    spill_response?: string;
    transport?: string;
  };
  faqs?: Array<{ q: string; a: string }>;
  cta?: { headline?: string; body?: string };
}

export interface SeoAssets {
  h1?: string;
  /** Where this product's canonical lives. Almost always the product's own
   *  path; see `resolveCanonicalSlug` for the one case that matters. */
  canonical_path?: string;
  focus_keyword?: string;
  headings?: Array<{ h2: string; h3: string[] }>;
  secondary_keywords?: string[];
  semantic_keywords?: string[];
  long_tail_keywords?: string[];
  buyer_intent_keywords?: string[];
  geographic_keywords?: string[];
  external_references?: Array<{ title: string; url: string }>;
  internal_links?: InternalLink[];
  open_graph?: { title?: string; description?: string; image_alt?: string };
  twitter?: { card?: string; title?: string; description?: string; image_alt?: string };
}

export interface InternalLink {
  path: string;
  title: string;
  /** Keyword-aware link text from the backend keyword engine. Falls back to
   *  `title` — anchors are varied deliberately, since 148 pages sharing one
   *  anchor phrase wastes the signal and reads as a footprint. */
  anchor?: string;
  reason?: string;
  type?: string;
}

export interface ImageSeo {
  alt?: string;
  title?: string;
  caption?: string;
  filename?: string;
}

/** Only routes that exist in `app/`. A suggestion pointing at a 404 would
 *  waste crawl budget and frustrate a buyer, so anything outside this set is
 *  dropped rather than rendered. */
const LINKABLE = /^\/(products|categories|blog)\/[^/]+$|^\/(categories|products|blog|contact|quote|how-we-work|about)$/;

export function isVerified(value?: string | null): boolean {
  return Boolean(value && value.trim() && value.trim() !== NEEDS_VERIFICATION);
}

/**
 * The slug this product's canonical URL should point at — its own, unless
 * `seo_assets.canonical_path` names a different, existing product.
 *
 * This is the duplicate-consolidation hook. The catalogue holds two records
 * for the same material ("Bentonite Powder" as both `bentonite-powder` under
 * Drilling Fluid Additives and `bentonite-powder-in-kenya` under Construction
 * Chemicals) sharing one focus keyword and one rendered title, so they
 * competed with each other for the same query and split the signals for it.
 * Pointing the newer record's canonical at the older one consolidates them
 * without deleting a row or breaking the Construction Chemicals listing: the
 * page stays live, linked and crawlable, and Google indexes one of them.
 *
 * `canonical_path` is written by the content generator and was self-
 * referential on all 176 products that carry it, so honouring it changes
 * nothing anywhere else. Two guards keep a bad generated value from
 * deindexing a live page: the path must be exactly `/products/<slug>`, and
 * that slug must exist in the catalogue. Anything else falls back to self.
 */
export function resolveCanonicalSlug(
  product: RawProduct,
  knownSlugs: ReadonlySet<string>,
): string {
  // Detail responses carry the whole `seo_assets` blob; list responses carry
  // only the flattened `canonical_path` string (see ProductListSerializer).
  // Both callers land here, so read either shape.
  const raw =
    (product.seo_assets as SeoAssets | undefined)?.canonical_path ??
    (product.canonical_path as string | undefined);
  const match = typeof raw === "string" ? raw.trim().match(/^\/products\/([a-z0-9-]+)\/?$/) : null;
  const target = match?.[1];
  return target && knownSlugs.has(target) ? target : product.slug;
}

/** Spec rows safe to show publicly — unverified placeholders removed. */
export function publicSpecs(sections: ContentSections): SpecRow[] {
  return (sections.specifications ?? []).filter((r) => isVerified(r.value));
}

/** Four availability states, with the schema.org term each maps to.
 *
 *  `LimitedAvailability` is the correct term for low stock, and `BackOrder`
 *  for goods brought in per order — both are still "you can buy this", which
 *  `OutOfStock` would wrongly deny. Older products predate the field and
 *  arrive as undefined, so the boolean is the fallback. */
const AVAILABILITY = {
  in_stock: { label: "In stock — Nairobi warehouse", schema: "https://schema.org/InStock" },
  low_stock: { label: "Low stock — confirm quantity when ordering", schema: "https://schema.org/LimitedAvailability" },
  on_request: { label: "Available on request", schema: "https://schema.org/BackOrder" },
  out_of_stock: { label: "Out of stock", schema: "https://schema.org/OutOfStock" },
} as const;

export function readAvailability(product: RawProduct): { label: string; schema: string } {
  const status = product.stock_status as keyof typeof AVAILABILITY | undefined;
  if (status && status in AVAILABILITY) return AVAILABILITY[status];
  return product.in_stock ? AVAILABILITY.in_stock : AVAILABILITY.out_of_stock;
}

export interface ProductView {
  /** True when the structured pipeline has produced content for this product. */
  structured: boolean;
  h1: string;
  summaryParagraphs: string[];
  keyFeatures: string[];
  benefits: Array<{ title: string; detail: string }>;
  specs: SpecRow[];
  grades: string[];
  gradesNote: string;
  packagingOptions: string[];
  applications: Application[];
  industries: Array<{ name: string; detail: string }>;
  typicalUses: Array<{ scenario: string; guidance: string }>;
  whyChooseUs: string[];
  availability: { label: string; schema: string };
  deliveryRegions: string[];
  deliveryNotes: string[];
  storage: string;
  safety: {
    guidance: string;
    ppe: string[];
    firstAid: string;
    spillResponse: string;
    transport: string;
  };
  faqs: Array<{ q: string; a: string }>;
  cta: { headline: string; body: string };
  internalLinks: InternalLink[];
  externalReferences: Array<{ title: string; url: string }>;
  imageSeo: ImageSeo;
}

type RawProduct = Record<string, any>;

export interface Application {
  use: string;
  /** Why this chemical is the one used there. Empty on products generated
   *  before applications carried a reason. */
  why: string;
}

/** Three shapes reach this, and all three have to render: `{use, why}` pairs
 *  from the current contract, plain strings from structured products generated
 *  before it, and the newline-separated `applications` column on products that
 *  predate the pipeline entirely. */
function readApplications(
  product: RawProduct,
  sections: ContentSections,
  structured: boolean,
): Application[] {
  const raw: Array<string | { use?: string; why?: string }> = structured
    ? (sections.applications ?? [])
    : String(product.applications ?? "").split("\n");
  return raw
    .map((item) =>
      typeof item === "string"
        ? { use: item.trim(), why: "" }
        : { use: String(item?.use ?? "").trim(), why: String(item?.why ?? "").trim() },
    )
    .filter((a) => a.use);
}

/** Resolve a product API payload into one view model, whichever generation
 *  produced it. */
export function readProduct(product: RawProduct): ProductView {
  const sections: ContentSections = product.content_sections ?? {};
  const seo: SeoAssets = product.seo_assets ?? {};
  const imageSeo: ImageSeo = product.image_seo ?? {};
  const structured = Boolean(sections.summary);

  // Legacy path: the flat `description` column is paragraph-separated prose,
  // `applications` is newline-separated. Same shapes the old page rendered.
  const summaryParagraphs = structured
    ? String(sections.summary ?? "").split(/\n\s*\n/).filter(Boolean)
    : String(product.description ?? "").split(/\n\s*\n/).filter(Boolean);

  const applications = readApplications(product, sections, structured);

  // Legacy products have no structured spec table, so build one from the flat
  // columns — that keeps the spec section identical to what shipped before.
  const legacySpecs: SpecRow[] = [
    { label: "CAS Number", value: product.cas_number },
    { label: "Chemical Formula", value: product.chemical_formula },
    { label: "Molecular Weight", value: product.molecular_weight },
    { label: "Density", value: product.density },
    { label: "Synonyms", value: product.synonyms },
    { label: "Grade", value: product.grade },
    { label: "Purity", value: product.purity },
    { label: "Appearance", value: product.appearance },
    { label: "UN Number", value: product.un_number },
    { label: "Signal Word", value: product.signal_word },
    { label: "Hazard Class", value: product.hazard_class },
    { label: "Hazard Statements", value: (product.hazard_statements ?? []).join("; ") },
    { label: "Packaging", value: product.packaging },
  ].filter((r) => isVerified(r.value)).map((r) => ({ ...r, verified: true }));

  // Staff-entered identifiers always win over anything the pipeline stored, so
  // a corrected CAS number or a transport classification typed into the admin
  // shows immediately without waiting for the page to be regenerated.
  const dbOverrides: SpecRow[] = [
    { label: "CAS Number", value: product.cas_number },
    { label: "Chemical Formula", value: product.chemical_formula },
    { label: "Molecular Weight", value: product.molecular_weight },
    { label: "Density", value: product.density },
    { label: "UN Number", value: product.un_number },
    { label: "Signal Word", value: product.signal_word },
    { label: "Hazard Class", value: product.hazard_class },
    { label: "Hazard Statements", value: (product.hazard_statements ?? []).join("; ") },
  ].filter((r) => isVerified(r.value));

  function mergeSpecs(rows: SpecRow[]): SpecRow[] {
    const merged = rows.map((row) => {
      const override = dbOverrides.find(
        (o) => o.label.toLowerCase() === row.label.toLowerCase());
      return override ? { ...row, value: override.value, verified: true } : row;
    });
    const missing = dbOverrides.filter(
      (o) => !merged.some((r) => r.label.toLowerCase() === o.label.toLowerCase()));
    return [...merged, ...missing.map((r) => ({ ...r, verified: true }))];
  }

  const internalLinks = (seo.internal_links ?? product.internal_links ?? []).filter(
    (l: InternalLink) => l?.path && LINKABLE.test(l.path),
  );

  return {
    structured,
    h1: seo.h1 || `${product.name} — Supplier in Kenya & East Africa`,
    summaryParagraphs,
    keyFeatures: sections.key_features ?? [],
    benefits: sections.benefits ?? [],
    specs: mergeSpecs(structured ? publicSpecs(sections) : legacySpecs),
    grades: sections.available_grades ?? [],
    gradesNote: sections.grades_note ?? "",
    packagingOptions: sections.packaging_options ?? [],
    applications,
    industries: sections.industries ?? [],
    typicalUses: sections.typical_uses ?? [],
    whyChooseUs: sections.why_choose_us ?? [],
    availability: readAvailability(product),
    deliveryRegions:
      sections.delivery_coverage?.regions ??
      String(product.regions ?? "").split(",").map((r: string) => r.trim()).filter(Boolean),
    deliveryNotes: sections.delivery_coverage?.notes ?? [],
    storage: sections.storage_guidelines ?? "",
    safety: {
      guidance: sections.handling_safety?.guidance || product.safety_info || "",
      ppe: sections.handling_safety?.ppe ?? [],
      firstAid: sections.handling_safety?.first_aid ?? "",
      spillResponse: sections.handling_safety?.spill_response ?? "",
      transport: sections.handling_safety?.transport ?? "",
    },
    faqs: (structured ? sections.faqs : product.faqs) ?? [],
    cta: {
      headline: sections.cta?.headline || `Order ${product.name}`,
      body: sections.cta?.body || "",
    },
    internalLinks,
    externalReferences: seo.external_references ?? [],
    imageSeo: {
      alt: imageSeo.alt || product.image_alt || "",
      title: imageSeo.title || product.name,
      caption: imageSeo.caption || "",
    },
  };
}
