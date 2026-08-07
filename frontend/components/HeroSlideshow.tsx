"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";

export type HeroImage = {
  src: string;
  alt: string;
  href: string;
  /** Only used for the accessible link name and the counter — never drawn
   * over the picture. */
  label: string;
};

const INTERVAL_MS = 6000;

/** Image-only hero.
 *
 * Deliberately carries no headline, body copy or scrim: the brief is to show
 * the uploaded category artwork clearly. Each slide is a link to its
 * category, so the band still navigates without any text sitting on top of
 * the photograph. Slide identity is exposed to assistive tech through the
 * link's accessible name and the counter beneath the arrows.
 */
export default function HeroSlideshow({ images }: { images: HeroImage[] }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const go = useCallback(
    (next: number) => setIndex(((next % images.length) + images.length) % images.length),
    [images.length],
  );

  useEffect(() => {
    if (paused || images.length < 2) return;
    timer.current = setInterval(() => setIndex((i) => (i + 1) % images.length), INTERVAL_MS);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [paused, images.length]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setPaused(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  if (images.length === 0) return null;

  return (
    <div
      className="hero-shots"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      role="region"
      aria-roledescription="carousel"
      aria-label="Product categories"
    >
      <div className="hero-shots-stage">
        {images.map((img, i) => (
          <Link
            key={img.src}
            href={img.href}
            className={`hero-shot ${i === index ? "is-active" : ""}`}
            aria-hidden={i !== index}
            tabIndex={i === index ? 0 : -1}
          >
            {/* Two copies of the same file: a blurred, over-scaled one fills
                the band edge-to-edge, and the sharp one is `contain`ed on top
                so the whole artwork is visible at every viewport ratio.
                next/image serves one request for both. */}
            <Image
              src={img.src}
              alt=""
              aria-hidden="true"
              fill
              sizes="100vw"
              priority={i === 0}
              className="hero-shot-fill"
            />
            <Image
              src={img.src}
              alt={img.alt}
              fill
              sizes="100vw"
              priority={i === 0}
              className="hero-shot-img"
            />
            <span className="visually-hidden">{img.label}</span>
          </Link>
        ))}
      </div>

      {images.length > 1 && (
        <>
          <button type="button" className="hero-arrow hero-arrow-prev"
                  aria-label="Previous category" onClick={() => go(index - 1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
          </button>
          <button type="button" className="hero-arrow hero-arrow-next"
                  aria-label="Next category" onClick={() => go(index + 1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m9 6 6 6-6 6" /></svg>
          </button>

          <div className="hero-shots-nav">
            {images.length <= 8 ? (
              <div className="hero-dots" role="tablist" aria-label="Choose category">
                {images.map((img, i) => (
                  <button
                    key={img.src} type="button" role="tab"
                    aria-selected={i === index} aria-label={img.label}
                    className={i === index ? "is-active" : ""}
                    onClick={() => go(i)}
                  />
                ))}
              </div>
            ) : (
              <div className="hero-counter" aria-live="polite">
                <strong>{String(index + 1).padStart(2, "0")}</strong>
                <span>/ {String(images.length).padStart(2, "0")}</span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
