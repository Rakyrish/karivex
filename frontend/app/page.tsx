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
      <div className="hero-band">
        <section className="hero">
          <span className="eyebrow">Strength behind every project</span>
          <h1>Industrial chemicals, delivered across <em>East Africa.</em></h1>
          <p>
            Bulk and small-pack supply from our {site.address.locality} warehouse — with{" "}
            {site.certifications.toLowerCase()}. {site.deliveryNairobi}, {site.deliveryRegional.toLowerCase()}.
          </p>
          <div className="hero-actions">
            <Link href="/quote" className="cta">Request a quote</Link>
            <a href={`tel:${site.phone}`} className="cta-ghost">Call {site.phone}</a>
          </div>
        </section>
      </div>

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
        <p><Link href="/products">View the full catalogue &rarr;</Link></p>
      </section>

      <section className="trust-strip" aria-label="Why buy from us">
        <ul>
          <li>
            <span className="trust-icon" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4z" /><path d="M9 12l2 2 4-4" /></svg>
            </span>
            <span>
              <strong>{site.certifications}</strong>
              <span>Full traceability on every batch</span>
            </span>
          </li>
          <li>
            <span className="trust-icon" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 3h13v13H1z" /><path d="M14 8h4l3 3v5h-7z" /><circle cx="5.5" cy="18.5" r="1.8" /><circle cx="17.5" cy="18.5" r="1.8" /></svg>
            </span>
            <span>
              <strong>{site.deliveryNairobi}</strong>
              <span>{site.deliveryRegional}</span>
            </span>
          </li>
          <li>
            <span className="trust-icon" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" /></svg>
            </span>
            <span>
              <strong>Serving {site.regions.join(", ")}</strong>
              <span>Bulk drums to small retail packs</span>
            </span>
          </li>
        </ul>
      </section>

      <section aria-labelledby="why-us" className="why-us">
        <div className="why-us-copy">
          <h2 id="why-us">A single, accountable chemical supplier for {site.regions.join(", ")}</h2>
          <p>
            Buying industrial chemicals across borders usually means juggling several distributors, each with
            different documentation standards and lead times. {site.shortName} runs one {site.address.locality}
            {" "}warehouse and one quote process for bulk drums and small retail packs alike, so procurement teams
            deal with a single point of contact from specification through delivery.
          </p>
          <p>
            Every order — bulk or small-pack — carries the same {site.certifications.toLowerCase()}, the same
            quoted lead times, and the same named contact for reordering. That consistency is what buyers actually
            need when a chemical is going into a production line or a water treatment process: predictable supply,
            not just a low price on day one.
          </p>
        </div>
        <ul className="why-us-list">
          <li><strong>One warehouse, one process</strong><span>Bulk and small-pack orders ship from the same {site.address.locality} facility, quoted the same way.</span></li>
          <li><strong>Documentation by default</strong><span>{site.certifications} — not an add-on, not something you have to request twice.</span></li>
          <li><strong>Human response times</strong><span>Quotes answered within one business hour, Mon&ndash;Sat EAT — by a person, not a ticket queue.</span></li>
          <li><strong>Cross-border delivery built in</strong><span>{site.deliveryNairobi}; {site.deliveryRegional.toLowerCase()}.</span></li>
        </ul>
      </section>

      <section aria-labelledby="process" className="process-strip">
        <h2 id="process">How sourcing works</h2>
        <ol className="process-steps">
          <li>
            <span className="process-num">1</span>
            <strong>Tell us what you need</strong>
            <span>Request a quote or place a small-pack order online.</span>
          </li>
          <li>
            <span className="process-num">2</span>
            <strong>We confirm specs &amp; pricing</strong>
            <span>Reply within one business hour, Mon&ndash;Sat EAT.</span>
          </li>
          <li>
            <span className="process-num">3</span>
            <strong>Dispatch from {site.address.locality}</strong>
            <span>{site.deliveryNairobi}, {site.deliveryRegional.toLowerCase()}.</span>
          </li>
          <li>
            <span className="process-num">4</span>
            <strong>Delivered with paperwork</strong>
            <span>{site.certifications} on every consignment.</span>
          </li>
        </ol>
      </section>

      <section aria-labelledby="grades" className="grades-strip">
        <h2 id="grades">Grades we supply</h2>
        <ul className="grades-list">
          <li><strong>Industrial / Technical</strong><span>Bulk process and manufacturing grades</span></li>
          <li><strong>Food Grade</strong><span>Safe for food &amp; beverage processing</span></li>
          <li><strong>Laboratory / Analytical</strong><span>Precision grades for testing and R&amp;D</span></li>
          <li><strong>Pharmaceutical</strong><span>Compliant grades for pharma production</span></li>
          <li><strong>Cosmetic Grade</strong><span>Formulation-ready cosmetic ingredients</span></li>
        </ul>
      </section>

      <section aria-labelledby="compliance" className="compliance-strip">
        <h2 id="compliance">Documentation that travels with every order</h2>
        <div className="compliance-grid">
          <div>
            <h3>Certificate of Analysis (COA)</h3>
            <p>
              Confirms the actual batch purity and specification against what was quoted — the reference
              document your QA team checks against on receipt.
            </p>
          </div>
          <div>
            <h3>Material Safety Data Sheet (MSDS)</h3>
            <p>
              Covers handling, storage and emergency guidance for the specific chemical you&rsquo;ve ordered —
              required for import clearance and internal safety compliance across {site.regions.join(", ")}.
            </p>
          </div>
          <div>
            <h3>Traceable batches</h3>
            <p>
              Every consignment is tied to a batch record, so a reorder or a query about a past delivery can be
              traced back to the exact specification you received.
            </p>
          </div>
        </div>
        <p className="compliance-note">
          Need documentation before you commit? Ask for the COA and MSDS when you <Link href="/quote">request a quote</Link> —
          they&rsquo;re included with the response, not just the shipment.
        </p>
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
