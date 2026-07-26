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

export interface AdminProduct extends AdminProductListItem {
  cas_number: string;
  synonyms: string;
  purity: string;
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
  mpesa_checkout_id: string;
  mpesa_receipt: string;
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
