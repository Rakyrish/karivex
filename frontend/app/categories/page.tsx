import type { Metadata } from "next";
import Link from "next/link";
import { getCategories, SITE_URL } from "@/lib/api";
import CategoryBrowser from "@/components/CategoryBrowser";
import { hasProducts } from "@/lib/categories";
import { site } from "@/lib/site";
import { ORG_ID, jsonLd } from "@/lib/schema";

// The 70 category pages previously had no hub: /categories itself was a 404,
// and sub-categories were reachable only from the mega-menu and footer, where
// they compete with every other sitewide link. This page gives every industry
// and every sub-category one clean, on-topic inlink from a page that is itself
// linked from the catalogue — the shortest crawl path from the homepage to a
// leaf category drops from three hops to two.
export const metadata: Metadata = {
  title: `Chemical Categories by Industry | ${site.shortName}`,
  description: `Every chemical category ${site.name} supplies — water treatment, food-grade, laboratory, paints, mining and more. ${site.certifications}.`,
  alternates: { canonical: `${SITE_URL}/categories` },
  openGraph: {
    title: `Chemical Categories by Industry | ${site.shortName}`,
    type: "website",
    url: `${SITE_URL}/categories`,
    images: [{ url: `${SITE_URL}/og?type=category&title=${encodeURIComponent("Chemical Categories")}`, width: 1200, height: 630 }],
  },
};

export default async function CategoriesIndexPage() {
  // Top-level only: each industry carries its own children, so one call
  // renders the whole two-level taxonomy.
  const industries = await getCategories();
  // Everything below counts and links only what is actually rendered. An
  // ItemList advertising categories the page does not link, or a heading
  // claiming 70 industries above a grid showing 30, is a contradiction a
  // crawler resolves against you.
  const stocked = industries.filter(hasProducts);

  const totalProducts = stocked.reduce((n, c) => n + c.total_product_count, 0);

  // Same shape as the individual category pages: the ItemList is bound to a
  // CollectionPage that resolves to the sitewide WebSite/Organization nodes,
  // so the hub is readable as this company's taxonomy rather than a floating
  // list of links.
  const url = `${SITE_URL}/categories`;
  const listId = `${url}#categories`;
  const breadcrumbId = `${url}#breadcrumb`;

  const hubGraph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": url,
        url,
        name: `Chemical Categories by Industry | ${site.shortName}`,
        description: `Every chemical category ${site.name} supplies — water treatment, food-grade, laboratory, paints, mining and more. ${site.certifications}.`,
        inLanguage: "en-KE",
        isPartOf: { "@id": `${SITE_URL}/#website` },
        breadcrumb: { "@id": breadcrumbId },
        publisher: { "@id": ORG_ID },
        ...(stocked.length > 0 && { mainEntity: { "@id": listId } }),
      },
      {
        "@type": "BreadcrumbList",
        "@id": breadcrumbId,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Categories", item: url },
        ],
      },
      ...(stocked.length > 0
        ? [
            {
              "@type": "ItemList",
              "@id": listId,
              name: "Chemical categories",
              numberOfItems: stocked.length,
              itemListOrder: "https://schema.org/ItemListUnordered",
              itemListElement: stocked.map((c, i) => ({
                "@type": "ListItem",
                position: i + 1,
                name: c.name,
                url: `${SITE_URL}/categories/${c.slug}`,
              })),
            },
          ]
        : []),
    ],
  };

  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(hubGraph) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <span aria-current="page">Categories</span>
      </nav>

      <h1>Chemical categories</h1>
      <p className="lede">
        {stocked.length} industries covering {totalProducts} products — from water treatment and food-grade
        additives to laboratory reagents, paints and mining inputs. {site.certifications}.{" "}
        <Link href="/products">Browse the full catalogue</Link> if you already know the chemical you need.
      </p>

      {/* Written copy, not filler. A hub page that is nothing but a link grid
          reads as thin to both buyers and crawlers — it asserts no expertise
          and answers no question. These three paragraphs explain how the
          taxonomy is organised, what grades and pack sizes to expect, and what
          happens when the chemical you need is not listed — the question the
          grid below actually provokes. Every claim here is drawn from site
          config or the real catalogue structure. */}
      <div className="cat-index-intro">
        <p>
          Chemicals here are grouped the way buyers search for them: by the industry that uses
          them, then by the job they do within it. Water treatment holds coagulants, flocculants,
          disinfectants and pH correctors; food and beverage holds preservatives, acidulants,
          sweeteners and processing aids. If you know the industry but not the exact product,
          start at the top level and work down — each industry page lists its sub-categories with
          current stock counts.
        </p>
        <p>
          Most categories span the same grade range, from technical through food, laboratory and
          pharmaceutical, and the majority of products are available both in bulk drums and in
          small retail packs. Every category listed below holds stock, and the count beside it is
          live. If what you need is not here we still source to order against your specification
          rather than holding it in {site.address.locality} — tell us the grade and volume and we
          will come back with pricing and lead time.
        </p>
        <p>
          Whichever route you take, the process is the same: send the specification, or simply
          describe the application and let us match it. We confirm grade, pack size, price and
          lead time in writing. {site.certifications} — the paperwork your QA team checks on
          receipt and customs needs at the border.{" "}
          <Link href="/how-we-work">See how we work</Link> for the full quote-to-delivery process.
        </p>
      </div>

      <CategoryBrowser industries={industries} />

    </section>
  );
}
