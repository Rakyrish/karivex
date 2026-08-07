import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/api";
import { site, decap } from "@/lib/site";
import { jsonLd } from "@/lib/schema";

export const metadata: Metadata = {
  title: `How We Work | ${site.name}`,
  description: `How ${site.shortName} sources and supplies chemicals across East Africa: the quote-to-delivery process, the grades we stock, and the COA/MSDS on every order.`,
  alternates: { canonical: `${SITE_URL}/how-we-work` },
  openGraph: {
    title: `How ${site.name} works`,
    type: "website",
    url: `${SITE_URL}/how-we-work`,
    images: [{ url: `${SITE_URL}/og?title=${encodeURIComponent("How we work")}`, width: 1200, height: 630 }],
  },
};

const breadcrumbSchema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
    { "@type": "ListItem", position: 2, name: "How we work", item: `${SITE_URL}/how-we-work` },
  ],
};

export default function HowWeWorkPage() {
  return (
    <section>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(breadcrumbSchema) }} />

      <nav aria-label="Breadcrumb" className="crumbs">
        <Link href="/">Home</Link> / <span aria-current="page">How we work</span>
      </nav>

      <h1>How we work</h1>
      <p className="lede">
        The practical detail behind every {site.shortName} order — how a quote becomes a delivery,
        which grades we stock, and the documentation that travels with each consignment.
      </p>

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
            Every order — bulk or small-pack — carries the same {decap(site.certifications)}, the same
            quoted lead times, and the same named contact for reordering. That consistency is what buyers actually
            need when a chemical is going into a production line or a water treatment process: predictable supply,
            not just a low price on day one.
          </p>
        </div>
        <ul className="why-us-list">
          <li><strong>One warehouse, one process</strong><span>Bulk and small-pack orders ship from the same {site.address.locality} facility, quoted the same way.</span></li>
          <li><strong>Documentation by default</strong><span>{site.certifications} — not an add-on, not something you have to request twice.</span></li>
          <li><strong>Human response times</strong><span>Quotes answered within one business hour, Mon&ndash;Sat EAT — by a person, not a ticket queue.</span></li>
          <li><strong>Cross-border delivery built in</strong><span>{site.deliveryNairobi}; {decap(site.deliveryRegional)}.</span></li>
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
            <span>{site.deliveryNairobi}, {decap(site.deliveryRegional)}.</span>
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


      <section className="about-cta" aria-labelledby="hww-cta">
        <h2 id="hww-cta">Ready to source something?</h2>
        <p>
          Send us the specification — or the application, if you&rsquo;re not sure which grade you need — and
          we&rsquo;ll come back within one business hour with pricing, lead time and the documentation.
        </p>
        <div className="hero-actions">
          <Link href="/quote" className="cta">Request a quote</Link>
          <Link href="/products" className="cta-ghost">Browse the catalogue</Link>
        </div>
      </section>
    </section>
  );
}
