import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { getCategories, getAllCategories, getFeaturedProducts, getLatestBlogPosts, getProducts, SITE_URL } from "@/lib/api";
import { site, decap } from "@/lib/site";
import { hasProducts } from "@/lib/categories";
import HeroCarousel, { type HeroSlide } from "@/components/HeroCarousel";
import HeroSlideshow, { type HeroImage } from "@/components/HeroSlideshow";
import IndustryTabs from "@/components/IndustryTabs";
import ProductCardActions from "@/components/ProductCardActions";

// The root layout supplies the title/description, but `alternates` is not
// inherited in a useful form — without this the homepage was the only URL on
// the site shipping no <link rel="canonical">, leaving Google to pick its own
// (the "Duplicate without user-selected canonical" class of report).
//
// Title/description are restated here rather than inherited so the homepage —
// the URL every "who is Karivex" query lands on — states the full legal name
// and the city in both fields, instead of relying on the sitewide default.
export const metadata: Metadata = {
  // Kept under 60 / 160 chars. Google truncates past that, and the truncated
  // tail is wasted — so the legal name and the city go first, where they
  // survive. "East Africa" stands in for the four-country list, which alone
  // cost 20 characters of the description.
  title: `${site.legalName} | Chemical Supplier Nairobi, Kenya`,
  description: `${site.legalName} is an industrial chemical distributor in Nairobi, Kenya. Bulk supply and procurement across East Africa. ${site.certifications}.`,
  alternates: { canonical: SITE_URL },
};

// The Organization/WebSite/LocalBusiness graph used to be declared here as
// well as in the layout, with both copies claiming the same @id. It now lives
// once in lib/schema.ts and is emitted sitewide from the root layout's <head>,
// so every page carries the identical entity — see the note in that file.

export default async function Home() {
  const [categories, allCategories, featured, posts, products] = await Promise.all([
    getCategories(),
    getAllCategories(),
    getFeaturedProducts(),
    getLatestBlogPosts(3),
    getProducts(),
  ]);

  // Industries with nothing filed under them are not linked from the homepage.
  // They render as a tile promising products, land on an empty grid, and read
  // as a soft 404 — the "broken page" symptom. They return automatically once
  // a product is filed under them.
  const stocked = categories.filter((c) => (c.total_product_count ?? 0) > 0);

  // The hero is a plain slideshow of the category artwork staff upload — shown
  // clean, with no copy or scrim over the picture. Each slide links through to
  // its category, where the image-plus-headline treatment lives instead.
  // Industries lead (they're the landing pages worth promoting), then any
  // sub-category with its own banner.
  // Stocked only. A hero slide is the most prominent link on the site, and
  // several were pointing at categories that render a heading over an empty
  // grid — the worst possible first click for a buyer, and a noindex dead end
  // for a crawler. Having a banner image is not the same as having stock.
  const categoryImages: HeroImage[] = [
    ...allCategories.filter((c) => c.image && c.parent === null && hasProducts(c)),
    ...allCategories.filter((c) => c.image && c.parent !== null && hasProducts(c)),
  ].map((c) => ({
    src: c.image!,
    alt: c.image_alt || c.name,
    href: `/categories/${c.slug}`,
    label: c.name,
  }));

  // Until categories have banners, fall back to the brand message so the hero
  // is never empty. Every claim here is a real Karivex commitment from site
  // config — not the "free shipping / money-back" badges stock templates ship.
  const fallbackSlides: HeroSlide[] = [
    {
      eyebrow: "Strength behind every project",
      // Slide 1 renders as the <h1> in this branch, so it names the company
      // outright rather than describing the product category anonymously.
      title: `${site.legalName} — industrial chemicals delivered across`,
      highlight: "East Africa.",
      body: `Bulk and small-pack supply from our ${site.address.locality} warehouse — with ${decap(site.certifications)}. ${site.deliveryNairobi}, ${decap(site.deliveryRegional)}.`,
      ctaHref: "/quote", ctaLabel: "Request a quote",
      altHref: `tel:${site.phone}`, altLabel: `Call ${site.phone}`,
      image: products.find((p) => p.image)?.image ?? null,
      imageAlt: "",
    },
    {
      eyebrow: "Documentation by default",
      title: "Every consignment ships with its",
      highlight: "COA & MSDS.",
      body: "Batch-traceable paperwork included with the quote, not just the delivery — the reference your QA team checks against on receipt and customs needs at the border.",
      ctaHref: "/quote", ctaLabel: "Ask for documentation",
      altHref: "/how-we-work", altLabel: "How we work",
      image: null, imageAlt: "",
    },
    {
      eyebrow: "Sixteen industries served",
      title: "From water treatment to",
      highlight: "food, paints & mining.",
      body: `Coagulants, solvents, food-grade additives, lab reagents and specialty inputs — one supplier, one quote process, serving ${site.regions.join(", ")}.`,
      ctaHref: "/products", ctaLabel: "Browse the catalogue",
      altHref: "/contact", altLabel: "Talk to us",
      image: null, imageAlt: "",
    },
  ];

  // HeroCarousel renders the page's <h1> itself, but only in the fallback
  // branch. In the image-hero branch nothing else does, so the identity band
  // below carries it; when the carousel is showing, the band steps down to
  // <h2> so the page never ships two competing top-level headings.
  const heroOwnsH1 = categoryImages.length === 0;
  const IdentityHeading = heroOwnsH1 ? "h2" : "h1";

  return (
    <>
      {/* Once any category has artwork the hero is pure imagery; until then the
          brand message stands in so the top of the page is never blank. */}
      {categoryImages.length > 0 ? (
        <HeroSlideshow images={categoryImages} />
      ) : (
        <div className="hero-band">
          <HeroCarousel slides={fallbackSlides} />
        </div>
      )}

      {/* Identity band. The image-only hero deliberately carries no copy, which
          left the homepage stating who this company is only in a
          visually-hidden <h1> — text that search engines discount and that
          extractors building company profiles routinely skip. This says it in
          visible prose instead, in the first block after the artwork: full
          legal name, what the company does, and where it trades, in the first
          sentence of the first paragraph. The wording mirrors the schema.org
          `description` on purpose — the copy and the structured data have to
          agree for either to be believed. */}
      <section className="identity-band" aria-labelledby="identity">
        <IdentityHeading id="identity">
          {site.legalName} — industrial chemical suppliers in {site.address.locality}, Kenya
        </IdentityHeading>
        <p className="identity-lede">
          <strong>{site.legalName}</strong> ({site.shortName}) is a premier industrial chemical
          distributor and procurement provider based in {site.address.locality}, Kenya. We handle
          bulk distribution, supply chain management and chemical procurement for manufacturers,
          processors and laboratories across {site.regions.join(", ")}.
        </p>
        <p>
          Registered and operating from {site.address.street}, {site.address.locality}, our
          warehouse ships bulk drums and small retail packs on the same quote process —
          with {decap(site.certifications)}, {decap(site.deliveryNairobi)} and{" "}
          {decap(site.deliveryRegional)}.
        </p>
      </section>

      <IndustryTabs industries={stocked} products={products} contact={site} />

      <section className="industry-band" aria-labelledby="industries">
        <div className="section-head">
          <h2 id="industries">Shop by category</h2>
          <p>{stocked.length} industries, each with its own specialist sub-categories — sourced and documented the same way.</p>
        </div>
        <ul className="industry-grid">
          {stocked.map((c, i) => (
            // Cards without an uploaded image fall back to one of four themed
            // gradients, cycled so neighbouring tiles never match — an empty
            // catalogue still reads as designed rather than broken.
            <li key={c.slug} className={`industry-card tone-${i % 4}`}>
              <Link href={`/categories/${c.slug}`}>
                <span className="industry-media">
                  {c.image ? (
                    // Blurred fill + contained shot, same treatment as the
                    // hero: the tile is a fixed 3:2 but the artwork isn't.
                    <>
                      <Image
                        src={c.image} alt="" aria-hidden
                        width={420} height={280} className="industry-media-fill"
                      />
                      <Image
                        src={c.image} alt={c.image_alt || c.name}
                        width={420} height={280} className="industry-media-shot"
                      />
                    </>
                  ) : (
                    <span className="industry-media-fallback" aria-hidden="true">
                      {c.name.charAt(0)}
                    </span>
                  )}
                  <span className="industry-count">
                    {`${c.total_product_count} product${c.total_product_count === 1 ? "" : "s"}`}
                  </span>
                </span>
                <span className="industry-body">
                  <strong>{c.name}</strong>
                  {c.children.length > 0 && (
                    <span className="industry-subs">
                      {c.children.slice(0, 4).map((k) => (
                        <span key={k.slug}>{k.name}</span>
                      ))}
                      {c.children.length > 4 && (
                        <span className="industry-subs-more">+{c.children.length - 4} more</span>
                      )}
                    </span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
        <p className="section-more"><Link href="/products">View the full catalogue &rarr;</Link></p>
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
          <li>
            <span className="trust-icon" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
            </span>
            <span>
              <strong>Quotes in one business hour</strong>
              <span>{site.hours} — answered by a person</span>
            </span>
          </li>
        </ul>
      </section>

      <section className="hww-teaser" aria-labelledby="hww-teaser-h">
        <div>
          <h2 id="hww-teaser-h">One supplier, one process, documented every time</h2>
          <p>
            Bulk drums and small retail packs move through the same {site.address.locality} warehouse
            and the same quote process — answered by a person within one business hour, and delivered
            with {decap(site.certifications)}.
          </p>
          <Link href="/how-we-work" className="cta">See how we work</Link>
        </div>
        <ul>
          <li><strong>1</strong><span>Tell us the spec or the application</span></li>
          <li><strong>2</strong><span>We confirm pricing &amp; lead time</span></li>
          <li><strong>3</strong><span>Dispatch from {site.address.locality}</span></li>
          <li><strong>4</strong><span>Delivered with COA &amp; MSDS</span></li>
        </ul>
      </section>

      {featured.length > 0 && (
        <section aria-labelledby="featured">
          <h2 id="featured">Featured products</h2>
          <ul className="product-grid">
            {featured.map((p) => (
              <li key={p.slug} className="product-card">
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
                  {p.is_small_pack && p.price_kes && <p>From KES {p.price_kes}</p>}
                </Link>
                <ProductCardActions productName={p.name} contact={site} />
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
