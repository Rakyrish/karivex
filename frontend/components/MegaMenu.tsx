"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { CategoryTreeItem } from "@/lib/api";

/** Industry-first mega-menu.
 *
 * Desktop: a persistent "Shop by industry" trigger opens a two-pane panel —
 * industries on the left, the hovered industry's chemical-function
 * sub-categories flying out on the right. Below the desktop breakpoint the
 * panel is replaced by a horizontally scrollable chip row, because a 16 x 4
 * grid is unusable on a phone.
 */
export default function MegaMenu({
  categories,
  quickLinks,
}: {
  categories: CategoryTreeItem[];
  quickLinks: Array<{ href: string; label: string }>;
}) {
  const [open, setOpen] = useState(false);
  // Empty categories are not linked anywhere on the site: a heading over an
  // empty grid is a soft 404, and they are already excluded from the sitemap
  // and noindexed. They reappear the moment a product is filed under them.
  const stocked = categories.filter((c) => (c.total_product_count ?? 0) > 0);
  const [activeId, setActiveId] = useState<number | null>(stocked[0]?.id ?? null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  // Route change closes the panel — otherwise it hangs over the new page.
  useEffect(() => { setOpen(false); }, [pathname]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") setOpen(false); }
    function onClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  useEffect(() => () => { if (closeTimer.current) clearTimeout(closeTimer.current); }, []);

  // A short grace period: moving the pointer diagonally from an industry to
  // its flyout briefly leaves the panel, which would otherwise snap shut.
  function scheduleClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpen(false), 180);
  }
  function cancelClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = null;
  }

  // Guard on `stocked`, not `categories`: a taxonomy that exists but holds no
  // products anywhere would otherwise render a menu with an empty panel and
  // crash on `active.name`.
  if (stocked.length === 0) return null;
  const active = stocked.find((c) => c.id === activeId) ?? stocked[0];

  return (
    <div className="mega-bar">
      <div className="mega-bar-inner">
        <div
          className="mega-root"
          ref={rootRef}
          onMouseEnter={() => { cancelClose(); setOpen(true); }}
          onMouseLeave={scheduleClose}
        >
          <button
            type="button"
            className={`mega-trigger ${open ? "is-open" : ""}`}
            aria-expanded={open}
            aria-haspopup="true"
            onClick={() => setOpen((o) => !o)}
          >
            <span className="mega-trigger-icon" aria-hidden="true"><span /><span /><span /></span>
            Shop by industry
            <svg className="mega-trigger-caret" width="12" height="12" viewBox="0 0 24 24"
                 fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"
                 strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </button>

          {open && (
            <div className="mega-panel">
              <ul className="mega-industries">
                {stocked.map((c) => (
                  <li
                    key={c.id}
                    className={c.id === active.id ? "is-active" : ""}
                    onMouseEnter={() => setActiveId(c.id)}
                  >
                    <Link href={`/categories/${c.slug}`} onFocus={() => setActiveId(c.id)}>
                      <span className="mega-industry-name">{c.name}</span>
                      {c.total_product_count > 0 && (
                        <span className="mega-count">{c.total_product_count}</span>
                      )}
                      {c.children.length > 0 && (
                        <svg className="mega-industry-caret" width="12" height="12" viewBox="0 0 24 24"
                             fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"
                             strokeLinejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>

              <div className="mega-flyout">
                <div className="mega-flyout-head">
                  <h3>{active.name}</h3>
                  {active.description && <p>{active.description}</p>}
                </div>
                {active.children.some((k) => (k.product_count ?? 0) > 0) ? (
                  <ul className="mega-subgrid">
                    {active.children.filter((k) => (k.product_count ?? 0) > 0).map((k) => (
                      <li key={k.id}>
                        <Link href={`/categories/${k.slug}`}>
                          {k.name}
                          {k.product_count > 0 && <span>{k.product_count}</span>}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mega-empty">Browse everything in this industry.</p>
                )}
                <Link href={`/categories/${active.slug}`} className="mega-flyout-cta">
                  View all {active.name} &rarr;
                </Link>
              </div>
            </div>
          )}
        </div>

        <nav className="mega-links" aria-label="Catalogue shortcuts">
          {quickLinks.map((l) => (
            <Link key={l.href} href={l.href}>{l.label}</Link>
          ))}
        </nav>
      </div>

      {/* Phone/tablet fallback — the two-pane panel doesn't fit a small screen.
          Iterates `stocked`, not `categories`: the desktop panel above has
          filtered empty categories since it was written, but this fallback did
          not, so every phone visitor (and every crawler rendering at a mobile
          viewport) still got all 70 — including the 39 that lead to an empty
          grid. Two paths rendering different link sets from one component is
          the bug; there is now one source for both. */}
      <nav className="mega-chips" aria-label="Product industries">
        <Link href="/products" className="category-chip category-chip-all">All products</Link>
        {stocked.map((c) => (
          <Link key={c.id} href={`/categories/${c.slug}`} className="category-chip">{c.name}</Link>
        ))}
      </nav>
    </div>
  );
}
