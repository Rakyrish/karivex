"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = { href: string; label: string; badge?: number };

export default function Sidebar({ unhandledQuotes, pendingOrders }: { unhandledQuotes: number; pendingOrders: number }) {
  const pathname = usePathname();

  const items: NavItem[] = [
    { href: "/admin", label: "Dashboard" },
    { href: "/admin/products", label: "Products" },
    { href: "/admin/categories", label: "Categories" },
    { href: "/admin/blog", label: "Blog" },
    { href: "/admin/quotes", label: "Quotes", badge: unhandledQuotes || undefined },
    { href: "/admin/orders", label: "Orders", badge: pendingOrders || undefined },
    { href: "/admin/seo", label: "SEO Health" },
  ];

  return (
    <nav className="admin-sidebar" aria-label="Admin navigation">
      <Link href="/admin" className="admin-sidebar-brand">
        <div>
          <strong>Karivex</strong>
          <span>Control Center</span>
        </div>
      </Link>
      <ul className="admin-nav">
        {items.map((item) => {
          const isActive = item.href === "/admin" ? pathname === "/admin" : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link href={item.href} aria-current={isActive ? "page" : undefined}>
                {item.label}
                {Boolean(item.badge) && <span className="admin-nav-badge">{item.badge}</span>}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="admin-sidebar-foot">Karivex Solutions Ltd</div>
    </nav>
  );
}
