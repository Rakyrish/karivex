import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getBlogPostsPage, SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";
import { ORG_ID, jsonLd } from "@/lib/schema";

type Props = { searchParams: Promise<{ page?: string }> };

// Page-aware canonical, same reasoning as app/products/page.tsx: a static
// canonical would mark every ?page=N as a duplicate of page 1 and strand the
// posts that only appear deeper in the series. Inert today (no posts are
// published yet, so pagination never renders) — correct before it matters.
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const canonical = page > 1 ? `${SITE_URL}/blog?page=${page}` : `${SITE_URL}/blog`;
  const base = `Buyer's Guides & Industry Insights`;
  const title = page > 1 ? `${base} — page ${page} | ${site.shortName}` : `${base} | ${site.shortName}`;
  // An index with nothing in it is a soft 404. Keep it out of the index until
  // there is something to read; `follow` preserves the nav links on the page.
  // Lifts itself with the first published post — same pattern as the empty
  // category pages, and paired with the filter in app/sitemap.ts.
  const { count } = await getBlogPostsPage(page);
  return {
    title,
    description: `Long-form guides on sourcing, handling and pricing industrial, food-grade and lab chemicals across ${site.regions.join(", ")}.`,
    alternates: { canonical },
    robots: count > 0 ? undefined : { index: false, follow: true },
    openGraph: {
      title,
      type: "website",
      url: canonical,
      images: [{ url: `${SITE_URL}/og?type=guide&title=${encodeURIComponent(base)}`, width: 1200, height: 630 }],
    },
  };
}

export default async function BlogIndexPage({ searchParams }: Props) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const { results, hasNext, hasPrevious, outOfRange } = await getBlogPostsPage(page);

  // Same unbounded soft-404 pagination space closed on /products — see the long
  // comment there for the reasoning and for why both guards are required.
  //
  // This index was already noindexing out-of-range pages, but only as a side
  // effect: the `count > 0` rule above exists to hide an *empty blog*, and an
  // out-of-range page happens to report count 0 because the failed request
  // degrades to an empty result. That coincidence breaks the moment the
  // fallback learns to preserve the real total. The explicit 404 below states
  // the intent directly, and leaves `count > 0` to mean only what it says.
  if (page > 1 && outOfRange) notFound();

  // Same shape as /products and /categories. The index carried no structured
  // data at all, which was harmless while it was empty and noindexed — it is
  // not now that it holds published posts and is in the sitemap.
  const canonical = page > 1 ? `${SITE_URL}/blog?page=${page}` : `${SITE_URL}/blog`;
  const listId = `${canonical}#posts`;
  const breadcrumbId = `${SITE_URL}/blog#breadcrumb`;

  const blogGraph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Blog",
        "@id": canonical,
        url: canonical,
        name: `Buyer's Guides & Industry Insights — ${site.shortName}`,
        description: `Long-form guides on sourcing, handling and pricing industrial, food-grade and lab chemicals across ${site.regions.join(", ")}.`,
        inLanguage: "en-KE",
        isPartOf: { "@id": `${SITE_URL}/#website` },
        breadcrumb: { "@id": breadcrumbId },
        publisher: { "@id": ORG_ID },
        ...(results.length > 0 && { mainEntity: { "@id": listId } }),
      },
      {
        "@type": "BreadcrumbList",
        "@id": breadcrumbId,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE_URL}/blog` },
        ],
      },
      ...(results.length > 0
        ? [
            {
              "@type": "ItemList",
              "@id": listId,
              name: "Buyer's guides",
              numberOfItems: results.length,
              itemListOrder: "https://schema.org/ItemListOrderDescending",
              itemListElement: results.map((p, i) => ({
                "@type": "ListItem",
                position: i + 1,
                name: p.title,
                url: `${SITE_URL}/blog/${p.slug}`,
              })),
            },
          ]
        : []),
    ],
  };

  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(blogGraph) }} />
      <h1>Buyer&rsquo;s guides &amp; industry insights</h1>
      <p className="lede">
        Practical sourcing guides for industrial, food-grade and laboratory chemical buyers in{" "}
        {site.regions.join(", ")}.
      </p>

      {results.length === 0 ? (
        <p>No posts published yet — check back soon.</p>
      ) : (
        <ul className="product-grid">
          {results.map((p) => (
            <li key={p.slug}>
              <Link href={`/blog/${p.slug}`}>
                {p.cover_image && (
                  <Image
                    src={p.cover_image}
                    alt={p.cover_image_alt}
                    width={400}
                    height={225}
                    style={{ width: "100%", height: "auto" }}
                  />
                )}
                <h2>{p.title}</h2>
                <p>{p.excerpt}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <nav className="pagination" aria-label="Blog pagination">
        {hasPrevious && <Link href={`/blog?page=${page - 1}`}>&larr; Newer posts</Link>}
        {hasNext && <Link href={`/blog?page=${page + 1}`}>Older posts &rarr;</Link>}
      </nav>
    </section>
  );
}
