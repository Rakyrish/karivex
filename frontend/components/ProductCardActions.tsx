// Call / WhatsApp actions on a product LISTING card.
//
// Replaces the "Request a quote" line the cards used to carry. That line was
// not a link — it described an action the buyer then had to go and find. These
// are real destinations: `tel:` dials, `wa.me` opens a chat already carrying
// the product name, so the enquiry arrives with context instead of "hi".
//
// Rendered as a SIBLING of the card's <Link>, never inside it: an anchor
// nested in an anchor is invalid HTML and browsers drop it, which would leave
// the buttons dead on the page.
//
// Server-rendered plain anchors, no client JS — the same reasoning as
// ProductContact on the detail page. Most buyers arrive from a phone search
// result, and the number has to be tappable in the initial HTML.
//
// Contact details arrive as PROPS rather than being read from `lib/site`.
// That file reads server-only `process.env` and says so at the top; one of
// these grids lives inside IndustryTabs, a "use client" component, where those
// vars are undefined and `site.phone` would fall back to the +254700000000
// placeholder — a dead number rendered on the homepage.

export interface CardContact {
  phone: string;
  whatsapp: string;
  shortName: string;
}

export default function ProductCardActions({
  productName, contact,
}: {
  productName: string;
  contact: CardContact;
}) {
  const site = contact;
  // wa.me wants digits only — a "+" or a space silently breaks the link.
  const waNumber = site.whatsapp.replace(/\D/g, "");
  const waText = encodeURIComponent(
    `Hello ${site.shortName}, I would like a quotation for ${productName}. `
    + `Please send price, pack sizes and lead time.`,
  );

  return (
    <div className="product-card-actions">
      <a
        className="product-card-btn is-call"
        href={`tel:${site.phone}`}
        aria-label={`Call ${site.shortName} about ${productName}`}
      >
        <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">
          <path d="M6.62 10.79a15.05 15.05 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.05-.24 11.4 11.4 0 0 0 3.57.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1 11.4 11.4 0 0 0 .57 3.57 1 1 0 0 1-.25 1.05z" />
        </svg>
        <span>Call</span>
      </a>

      <a
        className="product-card-btn is-whatsapp"
        href={`https://wa.me/${waNumber}?text=${waText}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`WhatsApp ${site.shortName} about ${productName}`}
      >
        <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">
          <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.65.08-.3-.15-1.25-.46-2.38-1.47-.88-.78-1.48-1.75-1.65-2.05-.17-.3-.02-.46.13-.61.14-.14.3-.35.45-.53.15-.18.2-.3.3-.5.1-.2.05-.38-.03-.53-.07-.15-.67-1.61-.92-2.21-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.53.08-.8.38-.28.3-1.05 1.02-1.05 2.5s1.08 2.9 1.23 3.1c.15.2 2.12 3.24 5.14 4.54.72.31 1.28.5 1.71.63.72.23 1.38.2 1.9.12.58-.09 1.75-.72 2-1.41.25-.7.25-1.29.17-1.41-.07-.13-.27-.2-.57-.35z" />
          <path d="M12.04 2C6.58 2 2.14 6.44 2.14 11.9c0 1.75.46 3.45 1.32 4.95L2 22l5.29-1.39a9.9 9.9 0 0 0 4.75 1.21h.01c5.46 0 9.9-4.44 9.9-9.9 0-2.64-1.03-5.13-2.9-6.99A9.82 9.82 0 0 0 12.04 2zm0 18.02h-.01a8.23 8.23 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23a8.2 8.2 0 0 1 5.83 2.42 8.18 8.18 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.24 8.23z" />
        </svg>
        <span>WhatsApp</span>
      </a>
    </div>
  );
}
