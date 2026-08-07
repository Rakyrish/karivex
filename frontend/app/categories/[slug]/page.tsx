import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import { getCategory, getCategories, getAllCategories, getProductsByCategory, SITE_URL } from "@/lib/api";
import { site, decap, clampDescription } from "@/lib/site";
import { stockedCategories, childHasProducts } from "@/lib/categories";
import { ORG_ID, jsonLd } from "@/lib/schema";
import ProductCardActions from "@/components/ProductCardActions";

export async function generateStaticParams() {
  // Every industry AND sub-category has its own landing page.
  const cats = await getAllCategories();
  return cats.map((c) => ({ slug: c.slug }));
}

type Props = { params: Promise<{ slug: string }> };

type CategoryLike = {
  name: string;
  meta_description?: string | null;
  description?: string | null;
  total_product_count: number;
};

/**
 * The category's meta description, resolved identically for the <meta> tag and
 * for the CollectionPage node. Keeping one function behind both matters: a
 * page whose schema describes it differently from its own snippet is a signal
 * mismatch a crawler has no way to reconcile.
 *
 * 64 of 70 categories have an empty `meta_description` and 53 have an empty
 * `description`, so this chain previously fell through to `undefined` and the
 * pages shipped no description at all — Google then wrote its own snippet from
 * whatever text it found. Composing from fields we always have (name, product
 * count, regions, certifications) guarantees every category page carries a
 * distinct, accurate description; staff-authored copy still wins when present.
 *
 * The clauses are in descending priority and are added greedily while the
 * result still fits 160 characters, so a long category name costs the
 * lowest-value clause rather than chopping the last one in half. The previous
 * `.join(" ").slice(0, 160)` shipped 18 snippets that ended mid-word —
 * "…COA & MSDS with every order. 24-hour delivery in Nai" — which is exactly
 * what a searcher read in the SERP.
 */
function categoryDescription(cat: CategoryLike): string {
  const composed = [
    `${cat.name} supplied across ${site.regions.join(", ")} by ${site.shortName}.`,
    cat.total_product_count > 0
      ? `${cat.total_product_count} product${cat.total_product_count === 1 ? "" : "s"} in stock.`
      : null,
    `${site.certifications}.`,
    `${site.deliveryNairobi}.`,
  ]
    .filter((clause): clause is string => Boolean(clause))
    .reduce((acc, clause) => {
      const next = acc ? `${acc} ${clause}` : clause;
      return next.length <= 160 ? next : acc;
    }, "");

  return clampDescription(cat.meta_description || cat.description || composed);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const cat = await getCategory(slug);
  if (!cat) return {};
  const url = `${SITE_URL}/categories/${slug}`;
  const description = categoryDescription(cat);
  return {
    title: cat.meta_title,
    description,
    alternates: { canonical: url },
    // An empty category renders a heading over an empty grid. Letting Google
    // index it produces a soft 404 and dilutes sitewide quality; `follow`
    // keeps any links on the page working as discovery paths. This lifts
    // itself the moment the category has stock — no manual step. Paired with
    // the same filter in app/sitemap.ts.
    robots: cat.total_product_count > 0 ? undefined : { index: false, follow: true },
    openGraph: {
      title: cat.meta_title,
      type: "website",
      url,
      images: [{ url: `${SITE_URL}/og?type=category&title=${encodeURIComponent(cat.name)}`, width: 1200, height: 630 }],
    },
  };
}

export default async function CategoryPage({ params }: Props) {
  const { slug } = await params;
  const cat = await getCategory(slug);
  if (!cat) notFound();
  const [products, categories] = await Promise.all([
    getProductsByCategory(slug),
    getCategories(),
  ]);
  // Stocked only. This band renders on all 31 indexable category pages, so an
  // unfiltered list was handing every one of them a set of links to categories
  // that are themselves noindexed and lead to an empty grid.
  const otherCategories = stockedCategories(categories).filter((c) => c.slug !== slug);
  const url = `${SITE_URL}/categories/${slug}`;
  const description = categoryDescription(cat);

  // A sub-category's parent is always a top-level industry (the taxonomy is
  // exactly two deep), so the industry list is enough to resolve it.
  const parent = cat.parent ? categories.find((c) => c.id === cat.parent) ?? null : null;
  // Stocked children only. These chips are the one place a child category was
  // still linked unfiltered — CategoryBrowser and the mega-menu flyout have
  // both filtered on `childHasProducts` since they were written, so a leaf like
  // `disinfectants-chlorination` was reachable from its parent's hero and
  // nowhere else. `product_count` is the child's own count, not a subtree
  // total, which is why this uses childHasProducts rather than hasProducts.
  // Annotation retained deliberately: getCategory() returns `any`, so without
  // it `.filter()` yields any[] and every `k` below is implicitly any.
  const subCategories: Array<{ slug: string; name: string; product_count: number }> =
    (cat.children ?? []).filter(childHasProducts);

  // One @graph rather than two loose blocks. The ItemList previously carried
  // url-only items and no @id, so it hung off the page unattached: a crawler
  // could see a list of URLs but nothing saying which page the list belongs
  // to, who published it, or what the entries are called. Naming the items and
  // binding the list to a CollectionPage — which in turn resolves to the
  // sitewide WebSite/Organization nodes emitted from the root layout — is what
  // makes this read as "this organisation's catalogue section" instead.
  const listId = `${url}#products`;
  const breadcrumbId = `${url}#breadcrumb`;

  const collectionGraph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": url,
        url,
        name: cat.meta_title || `${cat.name} — Suppliers in Kenya & East Africa`,
        description,
        inLanguage: "en-KE",
        isPartOf: { "@id": `${SITE_URL}/#website` },
        breadcrumb: { "@id": breadcrumbId },
        publisher: { "@id": ORG_ID },
        ...(products.length > 0 && { mainEntity: { "@id": listId } }),
        ...(cat.image && { primaryImageOfPage: cat.image }),
      },
      {
        "@type": "BreadcrumbList",
        "@id": breadcrumbId,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          // The visible breadcrumb shows Home / Parent / Category on a
          // sub-category; the markup said Home / Category. A trail that
          // disagrees with the one on the page is a mismatch Google flags,
          // and it hid the industry level from the breadcrumb rich result.
          ...(parent
            ? [
                {
                  "@type": "ListItem",
                  position: 2,
                  name: parent.name,
                  item: `${SITE_URL}/categories/${parent.slug}`,
                },
              ]
            : []),
          {
            "@type": "ListItem",
            position: parent ? 3 : 2,
            name: cat.name,
            item: url,
          },
        ],
      },
      ...(products.length > 0
        ? [
            {
              "@type": "ItemList",
              "@id": listId,
              name: `${cat.name} supplied by ${site.shortName}`,
              numberOfItems: products.length,
              itemListOrder: "https://schema.org/ItemListUnordered",
              itemListElement: products.map((p, i) => ({
                "@type": "ListItem",
                position: i + 1,
                name: p.name,
                url: `${SITE_URL}/products/${p.slug}`,
              })),
            },
          ]
        : []),
    ],
  };

  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(collectionGraph) }} />

      {/* Image-led banner. The artwork gets its own panel — beside the copy on
          desktop, above it on phones — so it is never cropped and never has
          type sitting on it. Without an uploaded image the block keeps its
          branded gradient so the page never looks half-built. */}
      <div className={`category-hero ${cat.image ? "has-image" : ""}`}>
        {cat.image && (
          <div className="category-hero-media">
            {/* Blurred over-scaled copy fills the panel behind the contained
                one; `fill` needs the positioned parent this div provides. */}
            <Image
              src={cat.image}
              alt=""
              aria-hidden
              fill
              sizes="(max-width: 64rem) 100vw, 42vw"
              priority
              className="category-hero-bg"
            />
            <Image
              src={cat.image}
              alt={cat.image_alt || cat.name}
              fill
              sizes="(max-width: 64rem) 100vw, 42vw"
              priority
              className="category-hero-shot"
            />
          </div>
        )}
        <div className="category-hero-inner">
          <nav aria-label="Breadcrumb" className="crumbs">
            <Link href="/">Home</Link>
            {" / "}
            {parent && (
              <>
                <Link href={`/categories/${parent.slug}`}>{parent.name}</Link>
                {" / "}
              </>
            )}
            <span aria-current="page">{cat.name}</span>
          </nav>

          {/* Same staggered entrance the homepage hero used to run — this is
              where that treatment now lives. */}
          <span className="eyebrow" data-anim="1">{parent ? parent.name : "Industry"}</span>
          <h1 data-anim="2">{cat.name} — Suppliers in Kenya &amp; East Africa</h1>
          <p className="lede" data-anim="3">
            {cat.description
              || `${cat.name} supplied across ${site.regions.join(", ")} — with ${decap(site.certifications)}. ${site.deliveryNairobi}.`}
          </p>
          <div className="hero-actions" data-anim="4">
            <Link href="/quote" className="cta">Request a quote</Link>
            <a href={`tel:${site.phone}`} className="cta-ghost">Call {site.phone}</a>
          </div>

          {subCategories.length > 0 && (
            <div className="category-hero-subs">
              {subCategories.map((k) => (
                <Link key={k.slug} href={`/categories/${k.slug}`}>
                  {k.name}
                  {k.product_count > 0 && <span>{k.product_count}</span>}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {products.length > 0 ? (
        <ul className="product-grid">
          {products.map((p) => (
            <li key={p.slug} className="product-card">
              <Link href={`/products/${p.slug}`}>
                {p.image && (
                  <Image src={p.image} alt={p.image_alt || p.name} width={300} height={200}
                         style={{ width: "100%", height: "auto" }} />
                )}
                <h2>{p.name}</h2>
                <p>{[p.purity, p.packaging].filter(Boolean).join(" · ")}</p>
                {p.is_small_pack && p.price_kes && <p>From KES {p.price_kes}</p>}
              </Link>
              <ProductCardActions productName={p.name} contact={site} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="lede">
          Nothing listed here yet — <Link href="/quote">request a quote</Link> and we&rsquo;ll source it for you.
        </p>
      )}

      {otherCategories.length > 0 && (
        <section aria-labelledby="other-categories" className="related-products">
          <h2 id="other-categories">Explore other categories</h2>
          <div className="category-nav-inner category-nav-inline">
            {otherCategories.map((c) => (
              <Link key={c.slug} href={`/categories/${c.slug}`} className="category-chip">
                {c.name}
              </Link>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
