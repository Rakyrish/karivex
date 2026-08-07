import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getProduct, getProducts, getRelatedProducts, SITE_URL } from "@/lib/api";
import { ORG_ID, jsonLd } from "@/lib/schema";
import { readProduct, resolveCanonicalSlug } from "@/lib/product-content";
import QuoteForm from "@/components/QuoteForm";
import ProductContact from "@/components/ProductContact";

// ISR: pages are static, purged by Django post_save -> /api/revalidate.
// No time-based revalidate needed; the webhook is the source of truth.
export const dynamicParams = true;

export async function generateStaticParams() {
  const products = await getProducts();
  return products.map((p) => ({ slug: p.slug }));
}

type Props = { params: Promise<{ slug: string }> };

// The catalogue slug set, used to validate `seo_assets.canonical_path` before
// it is allowed to point a canonical away from the page it is on. `getProducts`
// is the same cached fetch the root layout already issues on every render, so
// this costs no extra round trip.
async function knownSlugs(): Promise<ReadonlySet<string>> {
  return new Set((await getProducts()).map((p) => p.slug));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) return {};

  const canonicalUrl = `${SITE_URL}/products/${resolveCanonicalSlug(product, await knownSlugs())}`;
  const view = readProduct(product);
  const seo = product.seo_assets ?? {};
  const og = seo.open_graph ?? {};
  const twitter = seo.twitter ?? {};

  // Generated SEO assets take precedence over the flat columns.
  //
  // Structured content is applied without overwriting the flat
  // `description`/`faqs` prose (apply_flat=false), which deliberately leaves
  // the old `meta_title`/`meta_description` columns in place. Without this
  // preference the improved, length-corrected title never reached the page:
  // the first pilot published "Sulphuric Acid Supplier in Kenya | Karivex"
  // into seo_assets while the tab still read "Sulphuric Acid Kenya".
  const title = seo.meta_title || product.meta_title;
  const description =
    seo.meta_description ||
    product.meta_description ||
    `${product.name} supplied across ${product.regions}. COA & MSDS included. Request a quote from Karivex Solutions, Nairobi.`.slice(0, 160);
  const imageAlt = view.imageSeo.alt || product.image_alt;

  return {
    title,
    description,
    alternates: { canonical: canonicalUrl },
    openGraph: {
      title: og.title || title,
      description: og.description || description,
      type: "website",
      url: canonicalUrl,
      images: product.image
        ? [{ url: product.image, alt: og.image_alt || imageAlt }]
        : [{ url: `${SITE_URL}/og?type=product&title=${encodeURIComponent(product.name)}`, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: twitter.title || title,
      description: twitter.description || description,
      ...(product.image ? { images: [product.image] } : {}),
    },
  };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();

  const view = readProduct(product);
  const related = await getRelatedProducts(product.category?.slug, product.slug);
  // `url` is this page; `canonicalUrl` is the page Google should index. They
  // differ only for a duplicate record — see resolveCanonicalSlug. The Product
  // node hangs off the canonical so both records resolve to one entity, while
  // the WebPage node keeps describing the page actually being served.
  const url = `${SITE_URL}/products/${product.slug}`;
  const canonicalUrl = `${SITE_URL}/products/${resolveCanonicalSlug(product, await knownSlugs())}`;

  // Same precedence as generateMetadata: generated assets win, flat columns
  // are the fallback. Keeping these in step matters — the schema description
  // and the rendered snippet describing the page differently is a signal
  // mismatch a crawler has no way to reconcile.
  const seo = product.seo_assets ?? {};
  const schemaTitle = seo.meta_title || product.meta_title || product.name;
  const schemaDescription =
    seo.meta_description || product.meta_description || view.summaryParagraphs[0]?.slice(0, 300) || "";

  // --- Structured data. This is the moat: none of the four competitors emit
  // Product, FAQPage, or BreadcrumbList schema. Rich results = higher CTR.
  //
  // Driven off the resolved view model, so every VERIFIED spec row becomes a
  // PropertyValue and unverified placeholders are silently absent — a
  // "Requires manual verification" string must never be published as a
  // product attribute. Each property is independent: a product missing a CAS
  // number (e.g. a blend) must not also lose its purity/grade/packaging
  // markup, which an earlier version did by nesting all four behind one gate.
  const additionalProperty = view.specs.map((row) => ({
    "@type": "PropertyValue",
    name: row.label,
    value: row.value,
  }));

  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    "@id": `${canonicalUrl}#product`,
    name: product.name,
    description: schemaDescription,
    sku: product.slug,
    category: product.category?.name,
    ...(additionalProperty.length > 0 && { additionalProperty }),
    // A full ImageObject rather than a bare URL, so the generated caption and
    // alt text are actually machine-readable instead of sitting unused in the
    // database. Falls back to a plain URL string when there is no image SEO.
    ...(product.image && {
      image: view.imageSeo.caption || view.imageSeo.alt
        ? {
            "@type": "ImageObject",
            url: product.image,
            ...(view.imageSeo.caption && { caption: view.imageSeo.caption }),
            ...(view.imageSeo.alt && { description: view.imageSeo.alt }),
            ...(view.imageSeo.title && { name: view.imageSeo.title }),
          }
        : product.image,
    }),
    brand: { "@type": "Brand", name: "Karivex Solutions Ltd" },
    // Link the product to the sitewide entity rather than restating it, so
    // the seller resolves to the same node the rest of the site declares.
    manufacturer: { "@id": ORG_ID },
    // An Offer node must carry `price` (or `priceSpecification`) — currency
    // alone is a Rich Results *error* that suppresses the Product rich result
    // outright, so a price-less Offer is worse than no Offer. Quote-only
    // products therefore emit no `offers` at all; Search Console reports that
    // as "either offers, review, or aggregateRating should be specified",
    // which is accurate and unavoidable without real price or review data.
    // Fabricating either violates Google's policy, so this stays until real
    // prices land — at which point the Offer below appears automatically.
    //
    // Gated on price_kes alone, NOT on is_small_pack: is_small_pack now only
    // describes pack size, and any product carrying an indicative price is a
    // valid Offer worth marking up regardless of how it is packaged.
    ...(product.price_kes
      ? {
          offers: {
            "@type": "Offer",
            url: canonicalUrl,
            priceCurrency: "KES",
            price: product.price_kes,
            availability: view.availability.schema,
            areaServed: view.deliveryRegions,
            seller: { "@id": ORG_ID },
          },
        }
      : {}),
  };

  const faqSchema =
    view.faqs.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: view.faqs.map((f) => ({
            "@type": "Question",
            name: f.q,
            acceptedAnswer: { "@type": "Answer", text: f.a },
          })),
        }
      : null;

  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "@id": `${url}#breadcrumb`,
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: product.category.name, item: `${SITE_URL}/categories/${product.category.slug}` },
      { "@type": "ListItem", position: 3, name: product.name, item: url },
    ],
  };

  // Ties the page itself to the entity graph and the breadcrumb trail, which
  // is what lets a crawler read this URL as "a page about this product,
  // published by this organisation" rather than as a loose Product node.
  const webPageSchema = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": url,
    url,
    name: schemaTitle,
    description: schemaDescription,
    inLanguage: "en-KE",
    isPartOf: { "@id": `${SITE_URL}/#website` },
    about: { "@id": `${canonicalUrl}#product` },
    breadcrumb: { "@id": `${url}#breadcrumb` },
    publisher: { "@id": ORG_ID },
    ...(product.updated_at && { dateModified: product.updated_at }),
    ...(product.image && { primaryImageOfPage: product.image }),
  };

  return (
    <article className="product-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(productSchema) }} />
      {faqSchema && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(faqSchema) }} />
      )}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(breadcrumbSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(webPageSchema) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> /{" "}
        <Link href={`/categories/${product.category.slug}`}>{product.category.name}</Link> /{" "}
        <span aria-current="page">{product.name}</span>
      </nav>

      <header>
        <h1>{view.h1}</h1>
        <p className="lede">
          {product.purity && <>Purity {product.purity} · </>}
          {product.packaging && <>{product.packaging} · </>}
          Delivered across {view.deliveryRegions.join(", ")}
        </p>
      </header>

      {/* Two columns from 64rem up. The container is 96rem wide and every
          section used to stack down the left of it, so a desktop page was a
          narrow ribbon of prose against a half-empty viewport. The buying
          panel — photo, specifications, availability and the contact actions —
          now occupies that space and sticks while the copy scrolls, which is
          also where a buyer looks for it. Below 64rem it collapses back to one
          column in source order. */}
      <div className="product-layout">
        <div className="product-main">
      {/* Summary answers buyer intent before anything else on the page. */}
      <section aria-labelledby="about">
        <h2 id="about">About {product.name}</h2>
        {view.summaryParagraphs.map((para, i) => (
          <p key={i}>{para}</p>
        ))}
        {view.imageSeo.caption && <p className="image-caption">{view.imageSeo.caption}</p>}
      </section>

      {view.keyFeatures.length > 0 && (
        <section aria-labelledby="features">
          <h2 id="features">Key features</h2>
          <ul className="feature-list">
            {view.keyFeatures.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </section>
      )}

      {view.benefits.length > 0 && (
        <section aria-labelledby="benefits">
          <h2 id="benefits">Benefits</h2>
          <dl className="benefit-list">
            {view.benefits.map((b, i) => (
              <div key={i} className="benefit-item">
                <dt>{b.title}</dt>
                <dd>{b.detail}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {(view.grades.length > 0 || view.gradesNote) && (
        <section aria-labelledby="grades">
          <h2 id="grades">Available grades</h2>
          {view.grades.length > 0 && (
            <ul>
              {view.grades.map((g, i) => (
                <li key={i}>{g}</li>
              ))}
            </ul>
          )}
          {/* A one-item grade list tells a buyer nothing about whether it is
              the right material for their process. The note says which grade
              this listing is and what it suits. */}
          {view.gradesNote && <p>{view.gradesNote}</p>}
        </section>
      )}

      {view.packagingOptions.length > 0 && (
        <section aria-labelledby="packaging">
          <h2 id="packaging">Packaging options</h2>
          <ul>
            {view.packagingOptions.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Each application carries the reason this chemical is the one used
          there. Products generated before applications had a reason render as
          a plain list — the `why` is simply absent, not empty markup. */}
      {view.applications.length > 0 && (
        <section aria-labelledby="apps">
          <h2 id="apps">Applications</h2>
          {view.applications.some((a) => a.why) ? (
            <dl className="benefit-list">
              {view.applications.map((a, i) => (
                <div key={i} className="benefit-item">
                  <dt>{a.use}</dt>
                  {a.why && <dd>{a.why}</dd>}
                </div>
              ))}
            </dl>
          ) : (
            <ul>
              {view.applications.map((a, i) => (
                <li key={i}>{a.use}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {view.industries.length > 0 && (
        <section aria-labelledby="industries">
          <h2 id="industries">Industries served</h2>
          <div className="industries-grid">
            {view.industries.map((ind, i) => (
              <div key={i} className="industry-item">
                <h3>{ind.name}</h3>
                <p>{ind.detail}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Helps a buyer comparing options decide whether this is the right
          material for their job. Factual by contract — the generator may
          describe what each chemistry is used for, never claim superiority
          and never name a competing supplier. */}
      {view.typicalUses.length > 0 && (
        <section aria-labelledby="typical-uses">
          <h2 id="typical-uses">Typical industrial uses</h2>
          <dl className="benefit-list">
            {view.typicalUses.map((u, i) => (
              <div key={i} className="benefit-item">
                <dt>{u.scenario}</dt>
                <dd>{u.guidance}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {/* Assembled server-side from configured business data, never generated
          — so it cannot claim a certification Karivex does not hold. */}
      {view.whyChooseUs.length > 0 && (
        <section aria-labelledby="why-us">
          <h2 id="why-us">Why buy from Karivex</h2>
          <ul>
            {view.whyChooseUs.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      {view.deliveryRegions.length > 0 && (
        <section aria-labelledby="delivery">
          <h2 id="delivery">Delivery coverage</h2>
          <p>We supply {product.name} across {view.deliveryRegions.join(", ")}.</p>
          {view.deliveryNotes.length > 0 && (
            <ul>
              {view.deliveryNotes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {view.storage && (
        <section aria-labelledby="storage">
          <h2 id="storage">Storage guidelines</h2>
          <p>{view.storage}</p>
        </section>
      )}

      {view.safety.guidance && (
        <section aria-labelledby="safety">
          <h2 id="safety">Handling &amp; safety</h2>
          <p>{view.safety.guidance}</p>
          {/* SDS-sourced detail, shown only once staff have transcribed it.
              Nothing here is ever generated — a wrong first-aid instruction
              injures someone. */}
          {view.safety.firstAid && (
            <>
              <h3>First aid</h3>
              <p>{view.safety.firstAid}</p>
            </>
          )}
          {view.safety.spillResponse && (
            <>
              <h3>Spill response</h3>
              <p>{view.safety.spillResponse}</p>
            </>
          )}
          {view.safety.transport && (
            <>
              <h3>Transport</h3>
              <p>{view.safety.transport}</p>
            </>
          )}
          {view.safety.ppe.length > 0 && (
            <p>
              <strong>Recommended PPE:</strong> {view.safety.ppe.join(", ")}.
            </p>
          )}
          <p>MSDS and COA are supplied with every order.</p>
          {view.externalReferences.length > 0 && (
            <p className="external-refs">
              Further reading:{" "}
              {view.externalReferences.map((ref, i) => (
                <span key={ref.url}>
                  {i > 0 && ", "}
                  <a href={ref.url} rel="nofollow noopener" target="_blank">
                    {ref.title}
                  </a>
                </span>
              ))}
            </p>
          )}
        </section>
      )}

      {view.faqs.length > 0 && (
        <section aria-labelledby="faq">
          <h2 id="faq">Frequently asked questions</h2>
          {view.faqs.map((f, i) => (
            <details key={i}>
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </section>
      )}

        </div>

        {/* The buying panel. Everything a buyer checks before asking for a
            price, kept beside the copy instead of stacked below it. */}
        <aside className="product-aside">
          <div className="product-aside-inner">
            {/* Every product carries an image and generated image SEO
                (alt/title/caption/filename); `title` and the visible caption
                come from that, alt falls back to the product's own text. */}
            {product.image && (
              <figure className="product-figure">
                <Image
                  src={product.image}
                  alt={view.imageSeo.alt || product.image_alt || product.name}
                  title={view.imageSeo.title || product.name}
                  width={720}
                  height={540}
                  className="product-photo"
                  sizes="(max-width: 64rem) 100vw, 21rem"
                  priority
                />
                {view.imageSeo.caption && <figcaption>{view.imageSeo.caption}</figcaption>}
              </figure>
            )}

            {/* Only verified rows reach this table. An unconfirmed CAS number
                or purity figure is omitted rather than shown as a placeholder
                — a buyer orders against these values. */}
            {view.specs.length > 0 && (
              <section aria-labelledby="specs" className="spec-card">
                <h2 id="specs">Technical specifications</h2>
                <table>
                  <tbody>
                    {view.specs.map((row, i) => (
                      <tr key={i}>
                        <th scope="row">{row.label}</th>
                        <td>{row.value}</td>
                      </tr>
                    ))}
                    <tr>
                      <th scope="row">Availability</th>
                      <td>{view.availability.label}</td>
                    </tr>
                  </tbody>
                </table>
              </section>
            )}

            {/* Call / WhatsApp before the form: most buyers arrive from a
                phone search result, and a tap converts where a seven-field
                form does not. */}
            <ProductContact productName={product.name} />
          </div>
        </aside>
      </div>

      {/* Lateral crawl path. Without this a product page's only inlink was its
          category page, so link equity reaching each product sat at the site
          minimum and Google had no signal tying related chemicals together. */}
      {related.length > 0 && (
        <section aria-labelledby="related" className="related-band">
          <h2 id="related">More from {product.category?.name ?? "this category"}</h2>
          <ul className="related-list">
            {related.map((p) => (
              <li key={p.slug}>
                <Link href={`/products/${p.slug}`}>
                  <strong>{p.name}</strong>
                  {p.purity && <span>{p.purity}</span>}
                </Link>
              </li>
            ))}
          </ul>
          {product.category?.slug && (
            <p className="related-more">
              <Link href={`/categories/${product.category.slug}`}>
                View all {product.category.name} &rarr;
              </Link>
            </p>
          )}
        </section>
      )}

      {/* Editorial internal links, filtered to routes that actually exist. */}
      {view.internalLinks.length > 0 && (
        <nav aria-labelledby="more-links" className="internal-links">
          <h2 id="more-links">Useful links</h2>
          <ul>
            {view.internalLinks.map((l) => (
              <li key={l.path}>
                <Link href={l.path}>{l.anchor || l.title}</Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <section aria-labelledby="order" className="order-panel">
        <h2 id="order">{view.cta.headline}</h2>
        {view.cta.body && <p>{view.cta.body}</p>}
        {/* Quote-only by design: Karivex does not take payment on the site.
            The M-Pesa "Buy now" stub that used to sit here never charged
            anyone (it linked to this same form) and has been removed. */}
        <QuoteForm productId={product.id} productName={product.name} />
      </section>
    </article>
  );
}
