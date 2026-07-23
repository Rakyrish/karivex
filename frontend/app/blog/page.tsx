import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { getBlogPostsPage, SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: `Buyer's Guides & Industry Insights | ${site.shortName}`,
  description: `Long-form guides on sourcing, handling and pricing industrial, food-grade and lab chemicals across ${site.regions.join(", ")}.`,
  alternates: { canonical: `${SITE_URL}/blog` },
};

type Props = { searchParams: Promise<{ page?: string }> };

export default async function BlogIndexPage({ searchParams }: Props) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const { results, hasNext, hasPrevious } = await getBlogPostsPage(page);

  return (
    <section>
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
