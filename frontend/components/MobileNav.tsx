"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";

type NavLink = { href: string; label: string };

type Props = { links: NavLink[]; quoteHref: string; quoteLabel: string };

export default function MobileNav({ links, quoteHref, quoteLabel }: Props) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="mobile-nav">
      <button
        type="button"
        className="mobile-nav-toggle"
        aria-expanded={open}
        aria-controls="mobile-nav-panel"
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="mobile-nav-icon" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
      </button>

      {open && (
        <>
          <div className="mobile-nav-backdrop" onClick={() => setOpen(false)} />
          <nav id="mobile-nav-panel" className="mobile-nav-panel" aria-label="Mobile menu">
            {links.map((l) => (
              <Link key={l.href} href={l.href}>{l.label}</Link>
            ))}
            <Link href={quoteHref} className="mobile-nav-cta">{quoteLabel}</Link>
          </nav>
        </>
      )}
    </div>
  );
}
