// Server-side data layer. INTERNAL_API_URL is runtime-only (not a build ARG),
// so every fetch here runs in server components/route handlers at request or
// revalidation time — never at `next build`. That avoids the build-time fetch
// failure you hit before.
import { SITE_URL } from "./site";

export { SITE_URL };
const API = process.env.INTERNAL_API_URL ?? "http://karivex_backend:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}/api${path}`, { cache: "force-cache" });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

export interface ProductListItem {
  name: string; slug: string; category_slug: string; purity: string;
  packaging: string; is_small_pack: boolean; price_kes: string | null;
  featured: boolean;
  in_stock: boolean; image: string | null; image_alt: string; updated_at: string;
}

export interface BlogPostListItem {
  title: string; slug: string; excerpt: string;
  cover_image: string | null; cover_image_alt: string;
  published_at: string | null; updated_at: string;
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

export async function getCategories(): Promise<any[]> {
  return getListOrEmpty<any>(`/categories/`);
}

export async function getCategory(slug: string): Promise<any | null> {
  try {
    return await get(`/categories/${slug}/`);
  } catch {
    return null;
  }
}

export async function getProductsByCategory(slug: string): Promise<ProductListItem[]> {
  return getListOrEmpty<ProductListItem>(`/products/?category__slug=${slug}&page_size=200`);
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

export interface BlogPage {
  results: BlogPostListItem[];
  count: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
  hasPrevious: boolean;
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
    };
  } catch {
    return { results: [], count: 0, page, pageSize: BLOG_PAGE_SIZE, hasNext: false, hasPrevious: false };
  }
}

export async function getBlogPost(slug: string): Promise<any | null> {
  try {
    return await get(`/blog/${slug}/`);
  } catch {
    return null;
  }
}
