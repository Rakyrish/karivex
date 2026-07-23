import Link from "next/link";
import Image from "next/image";
import { getCategories, getFeaturedProducts, getLatestBlogPosts } from "@/lib/api";
import { site } from "@/lib/site";

export default async function Home() {
  const [categories, featured, posts] = await Promise.all([
    getCategories(),
    getFeaturedProducts(),
    getLatestBlogPosts(3),
  ]);

  return (
    <>
      <section className="hero">
        <h1>Industrial chemicals, delivered across East Africa.</h1>
        <p>
          Bulk and small-pack supply from our {site.address.locality} warehouse — with{" "}
          {site.certifications.toLowerCase()}. {site.deliveryNairobi}, {site.deliveryRegional.toLowerCase()}.
        </p>
        <Link href="/quote" className="cta">Request a quote</Link>
      </section>

      <section className="trust-strip" aria-label="Why buy from us">
        <ul>
          <li>
            <strong>{site.certifications}</strong>
            <span>Full traceability on every batch</span>
          </li>
          <li>
            <strong>{site.deliveryNairobi}</strong>
            <span>{site.deliveryRegional}</span>
          </li>
          <li>
            <strong>Serving {site.regions.join(", ")}</strong>
            <span>Bulk drums to small retail packs</span>
          </li>
        </ul>
      </section>

      <section id="categories">
        <h2>Product categories</h2>
        <ul className="product-grid">
          {categories.map((c) => (
            <li key={c.slug}>
              <Link href={`/categories/${c.slug}`}>
                <h3>{c.name}</h3>
                <p>{c.product_count} products</p>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {featured.length > 0 && (
        <section aria-labelledby="featured">
          <h2 id="featured">Featured products</h2>
          <ul className="product-grid">
            {featured.map((p) => (
              <li key={p.slug}>
                <Link href={`/products/${p.slug}`}>
                  {p.image && (
                    <Image
                      src={p.image}
                      alt={p.image_alt}
                      width={300}
                      height={200}
                      style={{ width: "100%", height: "auto" }}
                    />
                  )}
                  <h3>{p.name}</h3>
                  <p>{p.purity} · {p.packaging}</p>
                  <p>{p.is_small_pack && p.price_kes ? `From KES ${p.price_kes}` : "Request a quote"}</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {posts.length > 0 && (
        <section aria-labelledby="latest-guides">
          <h2 id="latest-guides">Latest buyer&rsquo;s guides</h2>
          <ul className="product-grid">
            {posts.map((post) => (
              <li key={post.slug}>
                <Link href={`/blog/${post.slug}`}>
                  {post.cover_image && (
                    <Image
                      src={post.cover_image}
                      alt={post.cover_image_alt}
                      width={300}
                      height={169}
                      style={{ width: "100%", height: "auto" }}
                    />
                  )}
                  <h3>{post.title}</h3>
                  <p>{post.excerpt}</p>
                </Link>
              </li>
            ))}
          </ul>
          <p><Link href="/blog">All guides &rarr;</Link></p>
        </section>
      )}
    </>
  );
}
