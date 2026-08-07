// Server-side data layer. INTERNAL_API_URL is runtime-only (not a build ARG),
// so every fetch here runs in server components/route handlers at request or
// revalidation time — never at `next build`. That avoids the build-time fetch
// failure you hit before.
import { SITE_URL } from "./site";

export { SITE_URL };
const API = process.env.INTERNAL_API_URL ?? "http://karivex-backend:8000";

// `cache: "force-cache"` with no `revalidate` gave these entries an unbounded
// TTL: once a response landed in the Data Cache it was never refetched, so
// /products served the two-product catalogue it was first rendered with while
// the API already returned 148. The revalidate webhook could not rescue it
// either — revalidatePath() never named /products (see catalog/signals.py).
// A 5-minute floor keeps the cache doing its job while guaranteeing the
// catalogue can never drift more than 5 minutes behind the database; the
// webhook still gives near-instant purges on top of it.
const API_REVALIDATE_SECONDS = 300;

/**
 * A non-OK API response, carrying the status so callers can tell "this record
 * does not exist" apart from "the backend is unreachable".
 *
 * That distinction is load-bearing for indexing, not just tidiness: every
 * helper below catches failures and degrades to an empty result, which is the
 * right behaviour for an outage (serve the page, lose nothing) and the wrong
 * one for a genuine 404 (serve a 200 that will be indexed as an empty page).
 * Without the status the two are indistinguishable and the safe fallback has
 * to be applied to both.
 */
class ApiError extends Error {
  constructor(readonly status: number, path: string) {
    super(`API ${path} -> ${status}`);
    this.name = "ApiError";
  }
}

/** True only for a definitive "no such resource" from the backend. */
export function isNotFound(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}/api${path}`, {
    next: { revalidate: API_REVALIDATE_SECONDS },
  });
  if (!res.ok) throw new ApiError(res.status, path);
  return res.json();
}

export interface ProductListItem {
  name: string; slug: string; category_slug: string; purity: string;
  packaging: string; is_small_pack: boolean; price_kes: string | null;
  featured: boolean;
  in_stock: boolean; image: string | null; image_alt: string; updated_at: string;
  /** Present for search. Buyers look products up by registry number and by
   *  alternative name at least as often as by the catalogue name. */
  category_name?: string;
  cas_number?: string;
  synonyms?: string;
  stock_status?: string;
}

export interface BlogPostListItem {
  title: string; slug: string; excerpt: string;
  cover_image: string | null; cover_image_alt: string;
  published_at: string | null; updated_at: string;
}

/** A catalogue category. The taxonomy is two levels: `parent === null` means
 * this is a top-level industry and `children` holds its chemical-function
 * sub-categories; a sub-category has a `parent` id and no children. */
export interface CategoryTreeItem {
  id: number;
  name: string;
  slug: string;
  description: string;
  product_count: number;
  /** Includes products filed on this category's sub-categories. */
  total_product_count: number;
  parent: number | null;
  display_order: number;
  /** Tile/banner image; null until staff upload one in the admin. */
  image: string | null;
  image_alt: string;
  children: Array<{
    id: number; name: string; slug: string; product_count: number;
    image: string | null; image_alt: string;
  }>;
}

// Build-time SSG (generateStaticParams, sitemap) runs with no backend up.
// Fall back to an empty list so the build succeeds; pages still render on
// first real request via ISR (dynamicParams: true) once the webhook data exists.
async function getListOrEmpty<T>(path: string): Promise<T[]> {
  try {
    const data: any = await get(path);
    return data.results ?? data ?? [];
  } catch (err) {
    console.warn(`[api] list fetch failed for ${path}, returning []:`, (err as Error).message);
    return [];
  }
}

export async function getProducts(): Promise<ProductListItem[]> {
  const out: ProductListItem[] = [];
  let page = 1;
  while (true) {
    let data: any;
    try {
      data = await get(`/products/?page=${page}`);
    } catch (err) {
      if (page === 1) console.warn(`[api] products fetch failed, returning []:`, (err as Error).message);
      break;
    }
    out.push(...data.results);
    if (!data.next) break;
    page++;
  }
  return out;
}

export async function getFeaturedProducts(): Promise<ProductListItem[]> {
  return getListOrEmpty<ProductListItem>(`/products/?featured=true&page_size=6`);
}

export async function getProduct(slug: string): Promise<any | null> {
  try {
    return await get(`/products/${slug}/`);
  } catch {
    return null;
  }
}

/** Top-level industries only, each with its sub-categories nested under
 * `children`. This is what the mega-menu, homepage grid and footer all want —
 * the unfiltered list also contains every sub-category, which would put 70
 * entries in the nav instead of 16. */
export async function getCategories(): Promise<CategoryTreeItem[]> {
  return getListOrEmpty<CategoryTreeItem>(`/categories/?top_level=1&page_size=100`);
}

/** Every category, industries and sub-categories alike — for pages that need
 * to resolve any slug (sitemap, category landing pages). */
export async function getAllCategories(): Promise<CategoryTreeItem[]> {
  return getListOrEmpty<CategoryTreeItem>(`/categories/?page_size=200`);
}

export async function getCategory(slug: string): Promise<any | null> {
  try {
    return await get(`/categories/${slug}/`);
  } catch {
    return null;
  }
}

export async function getProductsByCategory(slug: string): Promise<ProductListItem[]> {
  return getListOrEmpty<ProductListItem>(`/products/?category_tree=${slug}&page_size=200`);
}

/** Siblings in the same category, excluding the product itself.
 *
 * 134 of 148 product pages had exactly one internal inlink — their category
 * page — so link equity reaching any product sat at the site minimum and
 * there was no lateral crawl path between related items. Six is enough to
 * build a real cluster without turning the page into a link farm.
 *
 * The window is circular rather than `slice(0, limit)`. Taking the first six
 * every time would point every product in a category at the same six
 * siblings, so anything ranked seventh or later would still be reachable only
 * from the category page — the exact problem this is meant to solve. Starting
 * from each product's own position spreads inbound links evenly: in a
 * category larger than `limit`, every product ends up linked from exactly
 * `limit` siblings. */
export async function getRelatedProducts(
  categorySlug: string,
  excludeSlug: string,
  limit = 6,
): Promise<ProductListItem[]> {
  if (!categorySlug) return [];
  const siblings = await getProductsByCategory(categorySlug);
  const self = siblings.findIndex((p) => p.slug === excludeSlug);
  const others = siblings.filter((p) => p.slug !== excludeSlug);
  if (others.length <= limit) return others;
  const start = self < 0 ? 0 : self % others.length;
  return Array.from({ length: limit }, (_, i) => others[(start + i) % others.length]);
}

export async function getBlogPosts(): Promise<BlogPostListItem[]> {
  const out: BlogPostListItem[] = [];
  let page = 1;
  while (true) {
    let data: any;
    try {
      data = await get(`/blog/?page=${page}`);
    } catch {
      break;
    }
    out.push(...data.results);
    if (!data.next) break;
    page++;
  }
  return out;
}

export async function getLatestBlogPosts(limit: number): Promise<BlogPostListItem[]> {
  const data = await getListOrEmpty<BlogPostListItem>(`/blog/?page_size=${limit}`);
  return data.slice(0, limit);
}

export interface ProductPage {
  results: ProductListItem[];
  count: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
  hasPrevious: boolean;
  /**
   * The requested page number is past the end of the series — DRF answered 404.
   * Distinct from an empty `results` caused by an outage; see `isNotFound`.
   */
  outOfRange: boolean;
}

const PRODUCT_PAGE_SIZE = 16; // 4 rows of 4 on desktop, 8 rows of 2 on mobile

export async function getProductsPage(page: number): Promise<ProductPage> {
  try {
    const data: any = await get(`/products/?page=${page}&page_size=${PRODUCT_PAGE_SIZE}`);
    return {
      results: data.results ?? [],
      count: data.count ?? 0,
      page,
      pageSize: PRODUCT_PAGE_SIZE,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
      outOfRange: false,
    };
  } catch (e) {
    return {
      results: [], count: 0, page, pageSize: PRODUCT_PAGE_SIZE,
      hasNext: false, hasPrevious: false,
      outOfRange: isNotFound(e),
    };
  }
}

export interface BlogPage {
  results: BlogPostListItem[];
  count: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
  hasPrevious: boolean;
  /** See `ProductPage.outOfRange`. */
  outOfRange: boolean;
}

const BLOG_PAGE_SIZE = 9;

export async function getBlogPostsPage(page: number): Promise<BlogPage> {
  try {
    const data: any = await get(`/blog/?page=${page}&page_size=${BLOG_PAGE_SIZE}`);
    return {
      results: data.results ?? [],
      count: data.count ?? 0,
      page,
      pageSize: BLOG_PAGE_SIZE,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
      outOfRange: false,
    };
  } catch (e) {
    return {
      results: [], count: 0, page, pageSize: BLOG_PAGE_SIZE,
      hasNext: false, hasPrevious: false,
      outOfRange: isNotFound(e),
    };
  }
}

export async function getBlogPost(slug: string): Promise<any | null> {
  try {
    return await get(`/blog/${slug}/`);
  } catch {
    return null;
  }
}
