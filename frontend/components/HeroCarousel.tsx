"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

export type HeroSlide = {
  eyebrow: string;
  title: string;
  /** Rendered in the accent colour inside the headline. */
  highlight: string;
  body: string;
  ctaHref: string;
  ctaLabel: string;
  altHref?: string;
  altLabel?: string;
  /** Optional backdrop. Falls back to the branded gradient when absent. */
  image?: string | null;
  imageAlt?: string;
};

const INTERVAL_MS = 6500;

/** Auto-rotating hero, hand-rolled rather than pulled from a carousel library:
 * three slides of static markup don't justify the bundle cost, and this way
 * every slide stays in the DOM so search engines and screen readers get the
 * full copy regardless of which one is visible. */
export default function HeroCarousel({ slides }: { slides: HeroSlide[] }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const go = useCallback(
    (next: number) => setIndex(((next % slides.length) + slides.length) % slides.length),
    [slides.length],
  );

  useEffect(() => {
    if (paused || slides.length < 2) return;
    timer.current = setInterval(() => setIndex((i) => (i + 1) % slides.length), INTERVAL_MS);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [paused, slides.length]);

  // Respect users who've asked the OS for less motion: stop auto-advancing
  // and let them drive with the arrows/dots instead.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setPaused(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  if (slides.length === 0) return null;

  return (
    <div
      className="hero-carousel"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      role="region"
      aria-roledescription="carousel"
      aria-label="Highlights"
    >
      {/* Backdrops sit behind the whole carousel and cross-fade with a slow
          Ken Burns pan, so the motion reads as one continuous scene rather
          than a hard slide swap. */}
      <div className="hero-backdrops" aria-hidden="true">
        {slides.map((s, i) => (
          <div key={`bg-${s.title}`} className={`hero-backdrop ${i === index ? "is-active" : ""}`}>
            {s.image && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={s.image} alt="" />
            )}
          </div>
        ))}
      </div>

      <div className="hero-carousel-track">
        {slides.map((s, i) => (
          <section
            key={s.title}
            className={`hero-slide ${i === index ? "is-active" : ""}`}
            aria-hidden={i !== index}
            {...(i !== index ? { inert: "" as unknown as boolean } : {})}
          >
            {/* data-anim drives the staggered entrance: each element animates
                in on a short delay once its slide becomes active. */}
            <span className="eyebrow" data-anim="1">{s.eyebrow}</span>
            {/* Category slides carry only `highlight` (the category name);
                the brand slides split their headline across both fields.
                Only the first slide is the document's <h1> — every slide
                emitting one gave the page three competing top-level headings,
                which is invalid and leaves Google guessing which describes the
                page. The rest are <h2>; globals.css styles .hero-slide h1 and
                .hero-slide h2 identically, so the design is unchanged. */}
            {i === 0 ? (
              <h1 data-anim="2">
                {s.title ? <>{s.title} </> : null}
                <em>{s.highlight}</em>
              </h1>
            ) : (
              <h2 data-anim="2">
                {s.title ? <>{s.title} </> : null}
                <em>{s.highlight}</em>
              </h2>
            )}
            <p data-anim="3">{s.body}</p>
            <div className="hero-actions" data-anim="4">
              <Link href={s.ctaHref} className="cta">{s.ctaLabel}</Link>
              {s.altHref && s.altLabel && (
                <a href={s.altHref} className="cta-ghost">{s.altLabel}</a>
              )}
            </div>
          </section>
        ))}
      </div>

      {slides.length > 1 && (
        <div className="hero-progress" aria-hidden="true">
          <span key={`${index}-${paused}`} className={paused ? "is-paused" : ""} />
        </div>
      )}

      {slides.length > 1 && (
        <>
          <button type="button" className="hero-arrow hero-arrow-prev"
                  aria-label="Previous slide" onClick={() => go(index - 1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
          </button>
          <button type="button" className="hero-arrow hero-arrow-next"
                  aria-label="Next slide" onClick={() => go(index + 1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m9 6 6 6-6 6" /></svg>
          </button>
          {/* Dots work for a handful of slides; once the hero is driven by a
              full category list they'd become an unreadable row, so switch to
              a counter with the current category named. */}
          {slides.length <= 6 ? (
            <div className="hero-dots" role="tablist" aria-label="Choose slide">
              {slides.map((s, i) => (
                <button
                  key={s.highlight} type="button" role="tab"
                  aria-selected={i === index} aria-label={`Slide ${i + 1}: ${s.highlight}`}
                  className={i === index ? "is-active" : ""}
                  onClick={() => go(i)}
                />
              ))}
            </div>
          ) : (
            <div className="hero-counter" aria-live="polite">
              <strong>{String(index + 1).padStart(2, "0")}</strong>
              <span>/ {String(slides.length).padStart(2, "0")}</span>
              <em>{slides[index].highlight}</em>
            </div>
          )}
        </>
      )}
    </div>
  );
}
