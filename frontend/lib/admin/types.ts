export interface Stats {
  products: { total: number; in_stock_count: number; out_of_stock_count: number; featured_count: number };
  categories: { total: number };
  blog: { published_count: number; draft_count: number };
  quotes: { total: number; unhandled: number; last_7_days: number };
  orders: {
    total: number; pending: number; paid: number; delivered: number; cancelled: number; revenue_kes: string | number;
  };
  recent_activity: Array<
    | { type: "quote"; id: number; created_at: string; handled: boolean; summary: string }
    | { type: "order"; id: number; created_at: string; status: string; summary: string }
  >;
}

export interface SeoIssue {
  type: "product" | "category" | "blog";
  id: number;
  slug: string;
  name: string;
  field: string;
  issue: string;
}

export interface SeoAudit {
  score: number;
  checked_at: string;
  issue_count: number;
  issues: SeoIssue[];
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string;
  meta_title: string;
  meta_description: string;
  product_count: number;
  /** null = this is a top-level industry; otherwise the industry's id. */
  parent: number | null;
  display_order: number;
  image: string | null;
  image_alt: string;
}

export interface AdminProductListItem {
  id: number;
  name: string;
  slug: string;
  category: number;
  category_name: string;
  grade: string;
  price_kes: string | null;
  is_small_pack: boolean;
  in_stock: boolean;
  featured: boolean;
  image: string | null;
  updated_at: string;
}

/** Mirrors backend/ai_tools/content_schema.py. Staff edit these section by
 *  section; the public renderer reads the same shape via lib/product-content.ts. */
export interface ContentSections {
  summary: string;
  key_features: string[];
  benefits: Array<{ title: string; detail: string }>;
  specifications: Array<{ label: string; value: string; verified?: boolean }>;
  available_grades: string[];
  grades_note?: string;
  packaging_options: string[];
  /** Pairs since applications were re-typed to carry a reason. Products
   *  generated before that still hold plain strings. */
  applications: Array<{ use: string; why: string }> | string[];
  industries: Array<{ name: string; detail: string }>;
  typical_uses: Array<{ scenario: string; guidance: string }>;
  why_choose_us?: string[];
  delivery_coverage?: { regions: string[]; notes: string[] };
  storage_guidelines: string;
  handling_safety: {
    guidance: string;
    ppe: string[];
    /** Transcribed from the supplier SDS by staff. Never generated, and
     *  preserved across a regeneration. */
    first_aid?: string;
    spill_response?: string;
    transport?: string;
  };
  faqs: Array<{ q: string; a: string }>;
  cta: { headline: string; body: string };
}

export interface SeoAssets {
  meta_title?: string;
  meta_description?: string;
  h1?: string;
  focus_keyword?: string;
  headings?: Array<{ h2: string; h3: string[] }>;
  secondary_keywords?: string[];
  semantic_keywords?: string[];
  long_tail_keywords?: string[];
  buyer_intent_keywords?: string[];
  geographic_keywords?: string[];
  external_references?: Array<{ title: string; url: string }>;
  internal_links?: InternalLink[];
  canonical_path?: string;
}

export interface InternalLink {
  path: string;
  title: string;
  /** Keyword-aware link text; falls back to `title` when absent. */
  anchor?: string;
  reason?: string;
  type?: string;
}

/** Derived per product by backend/ai_tools/keywords.py before any copy is
 *  written. `candidates` is the derived menu; the groups that end up on
 *  `seo_assets` are what the page is actually optimised for. */
export interface KeywordPlan {
  primary: string;
  facets: {
    head: string;
    name: string;
    category: string;
    parent_category: string;
    family: string;
    grade: string;
    packaging: string[];
    industries: string[];
    related_products: string[];
  };
  geo: { countries: string[]; cities: string[]; macro: string[]; all: string[] };
  candidates: Record<string, string[]>;
}

/** Which surfaces the primary keyword actually reached. */
export interface KeywordPlacement {
  meta_title: boolean;
  meta_description: boolean;
  h1: boolean;
  first_100_words: boolean;
  summary: boolean;
  cta: boolean;
  slug: boolean;
}

export interface KeywordMetrics {
  primary_keyword: string;
  placement: KeywordPlacement;
  group_counts: Record<string, number>;
  section_density: Record<string, number>;
  stuffed_sections: string[];
  geo_allowed: string[];
}

export interface ContentIssue {
  /** `error` blocks publishing; `warning` is publishable but weaker. */
  severity: "error" | "warning";
  field: string;
  message: string;
}

export interface ContentReport {
  score: number;
  publishable: boolean;
  issues: ContentIssue[];
  /** Sections the pipeline automatically de-stuffed before validating. */
  rewritten_sections?: string[];
  metrics: {
    word_count: number;
    repetition_ratio: number;
    faq_count: number;
    filler_hits: number;
    unsupported_claims: number;
    pending_verification: string[];
    sections_present: number;
    sections_required: number;
    keywords?: KeywordMetrics | Record<string, never>;
  };
}

/** Full payload from POST /ai/structured-content/. */
export interface StructuredContent {
  image_analysis: Record<string, unknown>;
  sections: ContentSections;
  seo: SeoAssets;
  keyword_plan: KeywordPlan;
  image_seo: { alt: string; title: string; caption: string; filename: string };
  internal_links: InternalLink[];
  related_products: Array<{ slug: string; name: string; category: string }>;
  score: number;
  report: ContentReport;
  flat: {
    description: string;
    applications: string;
    safety_info: string;
    faqs: Array<{ q: string; a: string }>;
    meta_title: string;
    meta_description: string;
    image_alt: string;
  };
  applied?: boolean;
}

export interface AdminProduct extends AdminProductListItem {
  cas_number: string;
  synonyms: string;
  purity: string;
  chemical_formula: string;
  molecular_weight: string;
  /** Transport classification — staff entry only, never AI-generated. */
  un_number: string;
  hazard_class: string;
  stock_status: "in_stock" | "low_stock" | "on_request" | "out_of_stock";
  appearance: string;
  packaging: string;
  description: string;
  applications: string;
  safety_info: string;
  faqs: Array<{ q: string; a: string }>;
  small_pack_size: string;
  meta_title: string;
  meta_description: string;
  focus_keyword: string;
  regions: string;
  image_alt: string;
  ai_draft: Record<string, unknown>;
  ai_draft_generated_at: string | null;
  /** Empty object means this product still renders from the flat fields above. */
  content_sections: ContentSections | Record<string, never>;
  seo_assets: SeoAssets | Record<string, never>;
  image_seo: { alt?: string; title?: string; caption?: string; filename?: string };
  internal_links: InternalLink[];
  seo_score: number;
  content_report: ContentReport | Record<string, never>;
  content_generated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminBlogPost {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  body: string;
  cover_image: string | null;
  cover_image_alt: string;
  related_products: number[];
  meta_title: string;
  meta_description: string;
  published: boolean;
  published_at: string | null;
  updated_at: string;
  created_at: string;
}

export interface AdminQuote {
  id: number;
  product: number | null;
  product_name: string | null;
  name: string;
  company: string;
  email: string;
  phone: string;
  quantity: string;
  country: string;
  message: string;
  created_at: string;
  handled: boolean;
}

export interface AdminOrder {
  id: number;
  product: number;
  product_name: string;
  quantity: number;
  amount_kes: string;
  customer_name: string;
  phone: string;
  delivery_address: string;
  status: "pending" | "paid" | "delivered" | "cancelled";
  created_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface MediaLibraryItem {
  id: number;
  name: string;
  image: string;
  image_alt: string;
  updated_at: string;
}

export interface AIDraft {
  description: string;
  meta_title: string;
  meta_description: string;
  applications: string;
  safety_info: string;
  faqs: Array<{ q: string; a: string }>;
  image_alt: string;
}

/** Response of /dashboard/ai/product-from-url/ — an AIDraft plus the facts
 * the AI extracted from the pasted page and the photo(s) it found there. */
export interface ProductFromUrl extends AIDraft {
  name: string;
  category: string;
  category_id: number;
  grade: string;
  cas_number: string;
  synonyms: string;
  purity: string;
  appearance: string;
  packaging: string;
  focus_keyword: string;
  confidence: "high" | "medium" | "low";
  source_url: string;
  image_url: string;
  image_candidates: string[];
}
