import type { NextConfig } from "next";
import path from "path";
import dotenv from "dotenv";

// Single source of truth is the .env file at the project root (one level
// above frontend/). Next.js only auto-loads .env files from its own project
// root, so without this, `npm run dev`/`npm run build` outside Docker would
// see none of the SITE_*, INTERNAL_API_URL, etc. values. In Docker,
// docker-compose's `env_file: .env` already injects these before the process
// starts, and dotenv.config() never overrides an already-set variable — so
// this is a no-op there.
dotenv.config({ path: path.resolve(process.cwd(), "..", ".env") });

const config: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      // Any media served from the site's own origin fails next/image
      // optimisation unless its hostname is listed here. All catalogue images
      // currently come from Cloudinary, so nothing is broken today — but the
      // apex is the canonical host now, and the first Django-served /media/
      // upload would 400 without it. Both Karivex hosts are listed because the
      // subdomain still resolves and older records may carry absolute URLs.
      { protocol: "https", hostname: "karivexsolutionsltd.com" },
      { protocol: "https", hostname: "industrialchemicals.karivexsolutionsltd.com" },
      { protocol: "http", hostname: "karivex-backend" },
      { protocol: "https", hostname: "res.cloudinary.com" },
    ],
  },
  // RFC 8288 Link headers. Only relations backed by something that actually
  // exists are emitted: `canonical` duplicates the <link rel="canonical"> in
  // the HTML for agents that read headers without parsing the body (or issue
  // HEAD requests, where there is no body to parse at all).
  //
  // Deliberately NOT advertised here: api-catalog, service-desc, service-doc.
  // Those require a published OpenAPI document and API documentation, neither
  // of which this project has. A Link header pointing at a 404 is worse than
  // no header — it tells an agent a resource exists and then wastes its
  // request. Add them the same day the OpenAPI spec ships, not before.
  //
  // The security headers below are set here rather than in nginx on purpose:
  // Karivex does not own its nginx. Routing and TLS live in another repo's
  // config that also fronts two unrelated companies, where a syntax error
  // takes all three sites down. HSTS, X-Frame-Options, X-Content-Type-Options
  // and Referrer-Policy already come from there and are deliberately NOT
  // repeated here — duplicating a header emits it twice.
  async headers() {
    const origin = process.env.SITE_URL ?? "https://karivexsolutionsltd.com";

    // Every origin below is one the site actually loads; nothing is listed
    // speculatively. Cloudinary serves the catalogue photography, Ahrefs Web
    // Analytics is the one third-party script in the layout <head>, and every
    // browser-side POST (QuoteForm, ChatWidget) goes to a same-origin
    // /api/proxy/ path, so 'self' covers connect-src.
    //
    // On 'unsafe-inline' for scripts: the strict alternative is a per-request
    // nonce, and a nonce forces every page out of the static prerender into
    // dynamic rendering. These pages are ISR-prerendered — that trade would
    // cost the site its TTFB to buy a directive that, with Next's inline
    // hydration payload on every page, still could not be tightened to
    // 'strict-dynamic' without a rewrite. The directives that do not depend on
    // inline script — frame-ancestors, object-src, base-uri, form-action — are
    // where the real protection is here, and they are all locked down.
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'self'",
      "form-action 'self'",
      "script-src 'self' 'unsafe-inline' https://analytics.ahrefs.com",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://res.cloudinary.com",
      "font-src 'self' data:",
      "connect-src 'self' https://analytics.ahrefs.com",
      "frame-src 'self'",
      "manifest-src 'self'",
      "upgrade-insecure-requests",
    ].join("; ");

    // Explicitly surrenders capabilities the site never uses, so a future
    // injected script cannot reach for them either. `browsing-topics` opts the
    // domain out of the Topics API; `interest-cohort` is its dead FLoC
    // predecessor and is deliberately omitted rather than cargo-culted.
    const permissionsPolicy = [
      "accelerometer=()",
      "autoplay=()",
      "browsing-topics=()",
      "camera=()",
      "display-capture=()",
      "encrypted-media=()",
      "fullscreen=(self)",
      "geolocation=()",
      "gyroscope=()",
      "magnetometer=()",
      "microphone=()",
      "midi=()",
      "payment=()",
      "usb=()",
      "xr-spatial-tracking=()",
    ].join(", ");

    return [
      {
        source: "/",
        headers: [{ key: "Link", value: `<${origin}/>; rel="canonical"` }],
      },
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "Permissions-Policy", value: permissionsPolicy },
          // Googlebot renders with a real browser, so a page that trips CORP
          // on its own assets renders wrong. Same-site keeps the media and
          // chunk responses usable by this origin while refusing cross-origin
          // embedding by anyone else.
          { key: "Cross-Origin-Resource-Policy", value: "same-site" },
          { key: "X-DNS-Prefetch-Control", value: "on" },
        ],
      },
    ];
  },
  async rewrites() {
    // Browser-side form posts proxy through Next to the backend container.
    // Runtime env, container-name upstream — no shared aliases.
    return [
      {
        source: "/api/proxy/:path*",
        destination: `${process.env.INTERNAL_API_URL ?? "http://karivex-backend:8000"}/api/:path*`,
      },
    ];
  },
};

export default config;
