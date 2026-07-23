# Karivex Solutions Ltd — Chemical Division

Next.js 15 (App Router, ISR) + Django REST + Postgres + nginx, Docker Compose.
Built to outrank Kivi, Finstar, Zenco and Kiki's on speed, structured data and
content quality.

## Run locally

```bash
cp .env.example .env        # fill in POSTGRES_PASSWORD, DJANGO_SECRET_KEY, REVALIDATE_SECRET
docker compose build
docker compose up -d --force-recreate
docker compose exec karivex_backend python manage.py migrate
docker compose exec karivex_backend python manage.py loaddata seed
docker compose exec karivex_backend python manage.py createsuperuser
```

Admin: http://localhost/admin — add products there. Every save fires the
revalidation webhook, so the static page updates immediately. No stale cache.

## Architecture decisions (why it beats the competitors)

| Lever | Competitors | Karivex |
|---|---|---|
| Rendering | WordPress/WooCommerce, 3–6s loads | Static ISR pages, sub-second |
| Schema | None | Product + FAQPage + BreadcrumbList + ItemList + LocalBusiness |
| Content | Near-identical AI templates across all 4 sites | `description` field enforced unique, human-reviewed |
| Ordering | Zenco only has Buy Now | Quote for bulk + M-Pesa small packs (milestone 3) |
| Cache staleness | n/a | Django post_save -> /api/revalidate webhook |

Ops guardrails already baked in (from the alias-collision postmortem):
dedicated `karivex_net`, unique `container_name` everywhere, nginx upstreams
by container name, two-step deploy (`build` then `up -d --force-recreate`).

## SEO playbook (do these in order after launch)

1. **Google Search Console** — verify domain, submit `/sitemap.xml`.
2. **Google Business Profile** — "Chemical supplier" category, Nairobi address,
   phone matching the LocalBusiness schema. This wins the local pack, which
   none of the four competitors optimise.
3. **Content cadence** — 2 product pages/week minimum, each with unique 300+
   word descriptions and 4–6 real FAQs (they render as FAQPage rich results).
   NEVER paste manufacturer boilerplate — that's the competitors' duplicate-
   content trap.
4. **Buyer-intent blog** (add `/blog` in milestone 2): target
   "caustic soda price in Kenya", "where to buy hydrogen peroxide Nairobi",
   "sodium hypochlorite vs calcium hypochlorite for boreholes". Interlink to
   product pages.
5. **Backlinks** — Yellow Pages Kenya, BusinessList.co.ke, KAM directory,
   supplier profiles on Trademo/Kompass. Cheap, legitimate, and exactly the
   citations local rankings feed on.
6. **Title budget discipline** — meta_title <= 60 chars, meta_description
   <= 155. The model autogenerates compliant defaults; override per product
   when a keyword variant fits better.

## Roadmap

- **M1 (this repo):** catalog, quote flow, full schema markup, sitemap, ISR ✅
- **M2:** homepage design pass, blog, category long-form intros, OG images
- **M3:** M-Pesa Daraja STK push for small packs, order tracking, WhatsApp deep links
- **M4:** Swahili versions of top pages (`hreflang`), Uganda/Tanzania landing pages
