import type { MetadataRoute } from "next";
import { getProducts, getAllCategories, getBlogPosts, SITE_URL } from "@/lib/api";
import { resolveCanonicalSlug } from "@/lib/product-content";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [products, categories, posts] = await Promise.all([
    getProducts(),
    getAllCategories(),
    getBlogPosts(),
  ]);
  const productSlugs = new Set(products.map((p) => p.slug));
  return [
    { url: SITE_URL, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/products`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${SITE_URL}/categories`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/how-we-work`, changeFrequency: "monthly", priority: 0.7 },
    { url: `${SITE_URL}/about`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/contact`, changeFrequency: "monthly", priority: 0.6 },
    // Same soft-404 rule the categories below get: with no posts published,
    // /blog renders "No posts published yet" over an empty list. Advertising
    // an empty index invites the exact "Crawled – currently not indexed"
    // verdict this sitemap is trying to avoid. It reappears automatically with
    // the first published post. Matches the noindex rule in app/blog/page.tsx.
    ...(posts.length > 0
      ? [{ url: `${SITE_URL}/blog`, changeFrequency: "weekly" as const, priority: 0.7 }]
      : []),
    { url: `${SITE_URL}/quote`, changeFrequency: "monthly", priority: 0.5 },
    // 40 of the 70 categories currently hold no products at any depth, and
    // most also have no description — the rendered page is a heading and an
    // empty grid. Listing those in the sitemap asks Google to index 40 known
    // -empty pages, which is how a site earns "Soft 404" and "Crawled –
    // currently not indexed" at scale and drags down sitewide quality signals.
    // They stay crawlable and internally linked; they simply stop being
    // advertised until they have stock, at which point they reappear here
    // automatically. Matches the noindex rule in categories/[slug]/page.tsx.
    ...categories
      .filter((c) => c.total_product_count > 0)
      .map((c) => ({
        url: `${SITE_URL}/categories/${c.slug}`,
        changeFrequency: "weekly" as const,
        priority: 0.8,
        ...(c.image ? { images: [c.image] } : {}),
      })),
    // A page that canonicalises to a different URL must not be advertised
    // here: a sitemap entry is a request to index that exact URL, so listing a
    // known duplicate asks Google to index a page whose own canonical points
    // away — the "Alternate page with proper canonical tag" report, and a
    // contradiction between the two strongest indexing signals the site
    // sends. The duplicate stays crawlable and internally linked; it simply
    // stops being advertised. See resolveCanonicalSlug in lib/product-content.
    ...products
      .filter((p) => resolveCanonicalSlug(p, productSlugs) === p.slug)
      .map((p) => ({
        url: `${SITE_URL}/products/${p.slug}`,
        lastModified: new Date(p.updated_at),
        changeFrequency: "monthly" as const,
        priority: 0.9,
        // Image sitemap extension. Every catalogue photo is served from
        // Cloudinary and rendered through next/image, so the URL Googlebot
        // sees in the markup is a same-origin /_next/image?url=… wrapper —
        // discoverable, but it is the optimiser endpoint rather than the
        // image's own address. Naming the source here is what gives Google
        // Images a stable, canonical URL per product photo to index against.
        ...(p.image ? { images: [p.image] } : {}),
      })),
    ...posts.map((p) => ({
      url: `${SITE_URL}/blog/${p.slug}`,
      lastModified: new Date(p.updated_at),
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
