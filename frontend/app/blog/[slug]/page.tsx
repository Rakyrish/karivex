import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import { marked } from "marked";
import { getBlogPost, getBlogPosts, SITE_URL } from "@/lib/api";
import { site } from "@/lib/site";
import { ORG_ID, jsonLd } from "@/lib/schema";

export const dynamicParams = true;

export async function generateStaticParams() {
  const posts = await getBlogPosts();
  return posts.map((p) => ({ slug: p.slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await getBlogPost(slug);
  if (!post) return {};
  return {
    title: post.meta_title,
    description: post.meta_description || post.excerpt,
    alternates: { canonical: `${SITE_URL}/blog/${slug}` },
    openGraph: {
      title: post.meta_title,
      type: "article",
      url: `${SITE_URL}/blog/${slug}`,
      publishedTime: post.published_at,
      modifiedTime: post.updated_at,
      images: post.cover_image
        ? [{ url: post.cover_image, alt: post.cover_image_alt }]
        : [{ url: `${SITE_URL}/og?type=guide&title=${encodeURIComponent(post.title)}`, width: 1200, height: 630 }],
    },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = await getBlogPost(slug);
  if (!post) notFound();

  const url = `${SITE_URL}/blog/${slug}`;
  const bodyHtml = await marked.parse(post.body ?? "");

  const articleSchema = {
    "@context": "https://schema.org",
    // BlogPosting, not the generic Article: it is a subtype, so nothing is
    // lost, and it states what this actually is. `headline` is capped at 110
    // characters because Google truncates past that and an over-long headline
    // is a documented Article warning.
    "@type": "BlogPosting",
    "@id": `${url}#article`,
    headline: post.title.slice(0, 110),
    description: post.meta_description || post.excerpt,
    datePublished: post.published_at,
    dateModified: post.updated_at,
    // Both resolve to the sitewide entity by @id rather than restating the
    // company inline, so a post is attributable to the same Organization node
    // the rest of the site declares — which is the whole point of having one.
    author: { "@id": ORG_ID },
    publisher: { "@id": ORG_ID },
    ...(post.cover_image && { image: post.cover_image }),
    inLanguage: "en-KE",
    isPartOf: { "@id": `${SITE_URL}/#website` },
    mainEntityOfPage: url,
    // The products the post is written about. Without this the editorial
    // content and the catalogue are two unconnected islands to a crawler.
    ...(post.related_products?.length
      ? {
          about: post.related_products.map((p: { slug: string; name: string }) => ({
            "@type": "Product",
            "@id": `${SITE_URL}/products/${p.slug}#product`,
            name: p.name,
          })),
        }
      : {}),
  };

  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "@id": `${url}#breadcrumb`,
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE_URL}/blog` },
      { "@type": "ListItem", position: 3, name: post.title, item: url },
    ],
  };

  return (
    <article className="blog-post">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(articleSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(breadcrumbSchema) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <Link href="/blog">Blog</Link> /{" "}
        <span aria-current="page">{post.title}</span>
      </nav>

      <header>
        <h1>{post.title}</h1>
        {post.published_at && (
          <p className="lede">
            Published{" "}
            <time dateTime={post.published_at}>
              {new Date(post.published_at).toLocaleDateString("en-KE", { year: "numeric", month: "long", day: "numeric" })}
            </time>
          </p>
        )}
      </header>

      {post.cover_image && (
        <Image
          src={post.cover_image}
          alt={post.cover_image_alt}
          width={800}
          height={450}
          style={{ width: "100%", height: "auto" }}
          priority
        />
      )}

      {/* eslint-disable-next-line react/no-danger */}
      <div className="markdown-body" dangerouslySetInnerHTML={{ __html: bodyHtml }} />

      {post.related_products?.length > 0 && (
        <section aria-labelledby="related-products" className="related-products">
          <h2 id="related-products">Related products</h2>
          <ul className="product-grid">
            {post.related_products.map((p: any) => (
              <li key={p.slug}>
                <Link href={`/products/${p.slug}`}>
                  <h3>{p.name}</h3>
                  <p>View specifications &amp; request a quote &rarr;</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
