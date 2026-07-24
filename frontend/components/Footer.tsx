import Link from "next/link";

type CategoryItem = { name: string; slug: string };

type Props = {
  site: {
    name: string;
    shortName: string;
    tagline: string;
    legalName: string;
    phone: string;
    whatsapp: string;
    email: string;
    hours: string;
    regions: string[];
    certifications: string;
    address: { street: string; locality: string; region: string; country: string };
  };
  categories: CategoryItem[];
};

export default function Footer({ site, categories }: Props) {
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="footer-grid">
          <div className="footer-col footer-col-brand">
            <p className="footer-brand">{site.name}</p>
            <p className="footer-tagline">{site.tagline}</p>
            <p>
              Industrial, food-grade and laboratory chemical supply from our {site.address.locality} warehouse,
              delivered across {site.regions.join(", ")}. {site.certifications}.
            </p>
          </div>

          <div className="footer-col">
            <h3>Product categories</h3>
            <ul>
              {categories.slice(0, 8).map((c) => (
                <li key={c.slug}>
                  <Link href={`/categories/${c.slug}`}>{c.name}</Link>
                </li>
              ))}
              {categories.length === 0 && <li><Link href="/products">Browse all products</Link></li>}
            </ul>
          </div>

          <div className="footer-col">
            <h3>Company</h3>
            <ul>
              <li><Link href="/">Home</Link></li>
              <li><Link href="/about">About us</Link></li>
              <li><Link href="/products">Products</Link></li>
              <li><Link href="/blog">Buyer&rsquo;s guides</Link></li>
              <li><Link href="/quote">Request a quote</Link></li>
              <li><Link href="/contact">Contact</Link></li>
            </ul>
          </div>

          <div className="footer-col">
            <h3>Contact</h3>
            <ul className="footer-contact">
              <li><a href={`tel:${site.phone}`}>{site.phone}</a></li>
              <li><a href={`https://wa.me/${site.whatsapp.replace(/[^\d]/g, "")}`}>WhatsApp us</a></li>
              <li><a href={`mailto:${site.email}`}>{site.email}</a></li>
              <li>{site.address.street}, {site.address.locality}</li>
              <li>{site.hours}</li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; {year} {site.legalName}. All rights reserved.</p>
          <p>Serving {site.regions.join(", ")}</p>
        </div>
      </div>
    </footer>
  );
}
