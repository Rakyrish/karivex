"use client";
// Header search with live suggestions.
//
// The index is passed in from a server component (the layout already loads the
// product list), so there is no fetch on keystroke and no API to rate-limit.
// Submitting navigates to /search, which means the result is a real,
// linkable, shareable URL rather than transient client state.

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ProductListItem } from "@/lib/api";
import { searchProducts } from "@/lib/search";

export default function SearchBox({
  products, className = "", placeholder = "Search products, CAS number…",
}: {
  products: ProductListItem[];
  className?: string;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const router = useRouter();
  const boxRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const hits = query.trim().length >= 2 ? searchProducts(products, query).slice(0, 8) : [];

  // Clicking away closes the suggestions. Without this the panel stays open
  // over page content after the user has moved on.
  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const chosen = active >= 0 ? hits[active] : undefined;
    if (chosen) {
      router.push(`/products/${chosen.product.slug}`);
    } else if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
    setOpen(false);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, hits.length - 1));
      setOpen(true);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, -1));
    } else if (event.key === "Escape") {
      setOpen(false);
      setActive(-1);
    }
  }

  return (
    <div className={`site-search ${className}`} ref={boxRef}>
      <form role="search" onSubmit={submit}>
        <label className="visually-hidden" htmlFor={`${listId}-input`}>
          Search the chemical catalogue
        </label>
        <input
          id={`${listId}-input`}
          type="search"
          value={query}
          placeholder={placeholder}
          autoComplete="off"
          role="combobox"
          aria-expanded={open && hits.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(-1); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" aria-label="Search">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
               strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
        </button>
      </form>

      {open && query.trim().length >= 2 && (
        <ul className="site-search-results" id={listId} role="listbox">
          {hits.map((hit, i) => (
            <li key={hit.product.slug} role="option" aria-selected={i === active}
                className={i === active ? "is-active" : undefined}>
              <Link href={`/products/${hit.product.slug}`} onClick={() => setOpen(false)}>
                <strong>{hit.product.name}</strong>
                {hit.reason && <span className="site-search-reason">{hit.reason}</span>}
              </Link>
            </li>
          ))}
          {hits.length === 0 && (
            <li className="site-search-empty">
              No match for “{query.trim()}”. <Link href="/quote">Ask us to source it</Link>.
            </li>
          )}
          {hits.length > 0 && (
            <li className="site-search-all">
              <Link href={`/search?q=${encodeURIComponent(query.trim())}`}
                    onClick={() => setOpen(false)}>
                See all results for “{query.trim()}”
              </Link>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
