# Citations & backlinks — working sheet

Baseline taken **2026-08-07**. Verified by search, not assumed: `"Karivex
Solutions"`, `karivexsolutionsltd.com` and `"Karivex" Kenya chemicals` return
**zero third-party mentions**. The only off-site property that exists is the
Google Business Profile. The backlink profile is not weak — it is empty.

That is normal for a domain that became canonical on 2026-07-29, and it means
the sequencing below matters more than the volume.

---

## Read this before doing any of it

**Citations and backlinks are two different jobs.** Conflating them is why most
of this work gets done in the wrong order.

| | Citations | Editorial backlinks |
|---|---|---|
| What | Name/address/phone listings in directories | A real page choosing to link to you |
| Link value | Usually `nofollow`, near-zero ranking effect | The thing that actually moves rankings |
| What it fixes | *Does this company exist, and is it one entity?* | *Is this company worth ranking?* |
| Effort | Hours, mostly free | Months, needs something worth linking to |

Karivex's problem right now is the **first** one. Google resolved the brand name
to a different company for months (see the entity/SEO notes). Consistent
citations are what make an entity resolvable — that is why they come first, and
it is *not* because they will lift rankings. They mostly won't.

**Do not buy links, guest-post packages, or "DA50 backlinks" gigs.** They breach
Google's link-spam policy, they are trivially detectable on a domain with zero
existing profile, and the downside is a manual action on the only domain the
business has. Everything below is either a legitimate listing or an earned link.

---

## The canonical NAP block

Every submission uses **exactly** these strings. Character-for-character.

Inconsistent NAP is the single most common way a citation campaign produces
nothing: "Ltd" vs "Limited", `0742 355548` vs `+254742355548`, or a second
address variant, and the listings stop reinforcing one entity and start
describing several. One mismatched field is worse than one fewer listing.

Pulled live from the deployed JSON-LD on 2026-08-07, which is the source of
truth — **not** from the fallbacks in `frontend/lib/site.ts`, which differ (the
real postcode is `00400`, the fallback says `00100`).

```
Business name:     Karivex Solutions Ltd
Also known as:     Karivex · Karivex Solutions · Karivex Chemicals
Street:            Enterprise Road, Industrial Area
City:              Nairobi
Region:            Nairobi County
Postal code:       00400
Country:           Kenya (KE)
Primary phone:     +254 742 355548      (E.164: +254742355548)
Second phone:      +254 710 851911      (E.164: +254710851911)
Email:             info@karivexsolutionsltd.com
Website:           https://karivexsolutionsltd.com
Hours:             Mon–Fri 08:00–17:00, Sat 08:00–13:00
Serves:            Kenya, Uganda, Tanzania, Rwanda
Logo:              https://karivexsolutionsltd.com/brand/logo-512.png
```

**Website field: always the apex, always `https://`, never a trailing slash,
never the old `industrialchemicals.` subdomain.** The subdomain still 301s, but
a citation pointing at a redirect wastes the signal it exists to send.

Short description (fits most 150–160 char directory fields):

> Karivex Solutions Ltd is an industrial chemical distributor in Nairobi, Kenya
> — bulk supply, procurement and supply chain management across East Africa.

Long description (250–300 words needed by KAM/KNCCI-style profiles): reuse the
`/about` page copy verbatim rather than writing a variant.

Categories, in order of preference where a directory makes you pick:
Chemical Distributor → Chemical Supplier → Industrial Chemicals → Wholesaler.

---

## Priority order

### Tier 0 — free, this week, highest value

These are what make the entity resolvable. Nothing below matters until these
are done.

1. **LinkedIn company page** — still the top open item, still blocked on you.
   Free, and the single most-trusted `sameAs` target for a B2B company. Once it
   exists, append the URL to `SITE_SAME_AS` in `.env` — remember it is a Docker
   **build arg**, so it needs `docker compose build karivex_frontend`, not a
   restart.
2. **Google Business Profile** — exists (CID already in `sameAs`). Two things
   to confirm, both unverified: that the listing is genuinely yours, and that
   its Website field reads exactly `https://karivexsolutionsltd.com`. That
   field is the other half of the `sameAs` handshake; if it points anywhere
   else the two records do not connect.
   Then: complete every field, add products/services, post photos of the actual
   warehouse, and **start asking customers for reviews** — reviews are the
   strongest local-pack factor available and cost nothing.
3. **Bing Places** — free, imports directly from GBP, ~10 minutes.
   <https://www.bingplaces.com/>
4. **Apple Business Connect** — free. Feeds Apple Maps and Siri.

### Tier 1 — Kenyan directories (free or low cost)

All verified reachable on 2026-08-07. A `403` below means the host bot-blocks
scripted requests — it is live in a browser, not dead.

| Directory | URL | Status |
|---|---|---|
| Yellow Pages Kenya | <https://yellow.co.ke/> | 200 — use the **apex**, `www.` is NXDOMAIN |
| BusinessList Kenya | <https://businesslist.co.ke/> | 403 to curl, live |
| PigiaMe | <https://www.pigiame.co.ke/> | 403 to curl, live |
| Jiji Kenya | <https://jiji.co.ke/> | 403 to curl, live |
| KenyaPlex | <https://kenyaplex.com/> | 301 → live |
| Brabion | <https://brabion.com/> | 200 |

Yellow Pages Kenya is the pick of these — competitors (Bubanks, Euro Industrial
Chemicals) already rank through it, and it hosts supplier blog pages that pick
up long-tail queries.

### Tier 2 — trade bodies (paid, high trust, slower)

Real membership, real vetting, genuinely authoritative — and the listings are
sold, so treat these as a business decision rather than an SEO line item.

- **Kenya Association of Manufacturers** — the directory is
  <https://directory.kam.co.ke/> (verified; it runs on WooCommerce, so listings
  are a paid product). Note the `listings.kam.co.ke` URL that search results
  hand out is **NXDOMAIN** — do not chase it. Karivex distributes rather than
  manufactures, so confirm which membership category applies before paying.
- **KNCCI** — <https://www.kenyachamber.or.ke/> (verified). Nairobi chapter at
  <https://nairobichamber.co.ke/>. I did **not** verify the fee figures that
  search results quote for KNCCI; they looked implausible, so get them from the
  chamber directly rather than from anything summarised here.

### Tier 3 — chemical industry / B2B marketplaces

Lower trust, higher spam density — worth it for buyer discovery more than for
link value. Verified reachable:

- <https://www.chemical-distributors.com/> — already has a Kenya country page
- <https://www.go4worldbusiness.com/> — has a Kenya industrial-chemicals page
- <https://www.chemicalbook.com/> — supplier listings
- <https://ke.kompass.com/> — B2B, paid tiers

### Tier 4 — earned links (the part that actually ranks)

Nothing above will move a competitive term. This will, slowly.

The site already has the raw material: 181 products with real prose, and a blog.
What it lacks is a **reference asset** — something a third party has a reason to
link to instead of just read. Candidates, cheapest first:

- A **chemical compatibility / storage-segregation chart** for the products
  actually stocked. Safety officers link to these.
- A **CAS-number index** of the catalogue. Once the CAS backlog is filled (that
  work is blocked on your CSV, deliberately — no guessing), it becomes a
  genuinely useful lookup page.
- **Buyer's guides** with Kenya-specific pricing/import context. Nobody else is
  writing these for this market; the existing blog is the right vehicle.

Then the relationship links, which for a B2B distributor are usually the
easiest real links available: supplier and manufacturer partner pages, customer
case studies, and any industry press covering East African chemical supply.

---

## What to expect

Set against the timelines already agreed: brand queries days–3 weeks, local pack
2–8 weeks, long-tail product terms 3–9 months, head terms like "chemical
suppliers in Kenya" 12+ months if ever.

Citations accelerate the first two. They do close to nothing for the last two.
Anyone promising otherwise is selling something.

---

## Measurement

Do not judge this by "number of backlinks". Track:

1. **Search Console → Links** — the only first-party link data available, free.
2. A monthly `"Karivex Solutions"` search — the baseline today is zero results;
   the first real signal of progress is that query returning Karivex properties.
3. GBP insights — calls and direction requests, which is what local citations
   are actually for.
