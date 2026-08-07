# Directory submission copy — ready to paste

Companion to `docs/seo-citations.md`, which holds the canonical NAP block and
the target list. **Use the NAP block there for every name/address/phone field.**
This file is only the prose.

Every claim below is drawn from copy already published on the site (`/about`,
`/how-we-work`, the category tree). Nothing is invented.

**What is deliberately NOT claimed anywhere here — do not add it:** founding
year, employee count, revenue, ISO/any certification, client names, "market
leader". None of it is on the site, none of it was supplied, and a directory
profile is exactly the kind of record that outlives the person who wrote it and
gets quoted back as fact. If any of these are true, send them over and they can
be added deliberately.

**On numbers:** the catalogue moves (182 products / 31 stocked categories as of
2026-08-07). Copy below says "180+" and "30+" so a listing nobody revisits does
not slowly become false. Do not paste exact counts into directories.

---

## 1. Short description — 150–160 chars

Most directory "tagline" / meta fields.

> Karivex Solutions Ltd is an industrial chemical distributor in Nairobi, Kenya — bulk supply, procurement and supply chain management across East Africa.

*(152 characters, measured.)*

---

## 2. Google Business Profile description — 750 char limit

GBP truncates hard at 750. This is **709**, measured — paste it whole.

> Karivex Solutions Ltd is an industrial chemical distributor in Industrial Area, Nairobi. We supply industrial, food-grade, laboratory, pharmaceutical and cosmetic-grade chemicals from a single Nairobi warehouse, delivered across Kenya, Uganda, Tanzania and Rwanda.
>
> Our catalogue spans bulk process chemicals through to small retail packs across 30+ categories — water treatment, solvents and thinners, paints, inks and coatings, construction chemicals, food-grade additives, cleaning and hygiene, and adhesives and sealants.
>
> Bulk and small-pack orders move through the same quote process, answered within one business hour. COA and MSDS documentation comes with every order as standard, not as a paid extra.

---

## 3. Medium description — ~150 words

For directories with a 1,000–1,500 character body.

> Karivex Solutions Ltd is the chemical division supplying industrial,
> food-grade, laboratory, pharmaceutical and cosmetic-grade chemicals from a
> single Nairobi warehouse, delivered across Kenya, Uganda, Tanzania and Rwanda.
>
> The catalogue spans bulk process chemicals through to small retail packs,
> organised by category rather than by manufacturer — so a buyer looking for
> water treatment chemicals, solvents or construction additives can compare
> specifications directly. Every product carries its own purity, packaging and
> CAS reference rather than a shared manufacturer data sheet copied across
> similar products.
>
> Bulk and small-pack orders both move through the same warehouse and the same
> quote process, answered within one business hour. Delivery is same-day to
> 24-hour within Nairobi and 2–3 days to Uganda, Tanzania and Rwanda — the same
> lead times whether the order is a single drum or a full truckload.
>
> COA and MSDS documentation is issued with every order as standard.

---

## 4. Long description — 250–300 words

For KAM / KNCCI / Kompass-style profiles with a substantial body field.

> **Karivex Solutions Ltd — industrial chemical distribution, Nairobi**
>
> Karivex Solutions Ltd is an industrial chemical distributor operating from
> Enterprise Road, Industrial Area, Nairobi. The company supplies industrial,
> food-grade, laboratory, pharmaceutical and cosmetic-grade chemicals to
> manufacturers, processors and institutional buyers across Kenya, Uganda,
> Tanzania and Rwanda.
>
> The catalogue covers more than 180 products across 30+ categories, including
> water treatment chemicals, solvents and thinners, paints, inks and coatings,
> construction chemicals, food-grade additives and acidity regulators, cleaning
> and hygiene chemicals, adhesives and sealants, cosmetic and detergent raw
> materials, agriculture and animal feed inputs, pigments and fillers, and
> plastics and rubber additives.
>
> It is organised by chemical function rather than by manufacturer, so a buyer
> can compare specifications directly across suppliers instead of working
> through separate manufacturer catalogues. Every product carries its own
> purity, packaging and CAS reference rather than a shared data sheet copied
> across similar items.
>
> Karivex supplies both bulk process quantities and small retail packs through
> the same warehouse and the same quote process. Quotations are answered within
> one business hour during working hours. Delivery is 24-hour within Nairobi
> and 2–3 days to Uganda, Tanzania and Rwanda, at the same lead times whether
> the order is a single drum or a full truckload.
>
> Certificates of Analysis and Material Safety Data Sheets are issued with
> every order as standard rather than as a paid add-on — batch documentation is
> treated as part of the product, because a chemical without traceable
> specifications is a liability for whoever receives it next in the supply
> chain.
>
> Enquiries: +254 742 355548 · info@karivexsolutionsltd.com ·
> https://karivexsolutionsltd.com

---

## 5. Category selections

Directories rarely offer the exact right category. Pick in this order, taking
the first one the directory actually has:

**Primary:**
1. Chemical Distributors
2. Chemical Suppliers
3. Industrial Chemicals
4. Chemicals — Wholesale
5. Chemicals (generic)

**Secondary / additional (where multiple are allowed):**
- Water Treatment Chemicals / Water Treatment Equipment & Supplies
- Paint & Coating Raw Materials
- Food Ingredients & Additives
- Construction Chemicals & Admixtures
- Cleaning & Janitorial Supplies
- Laboratory Chemicals & Reagents
- Cosmetic & Detergent Raw Materials
- Adhesives & Sealants
- Agricultural Inputs

**Do not** select: Chemical Manufacturers, Chemical Manufacturing. Karivex
distributes; it does not manufacture. Miscategorising there is the kind of
thing a trade body checks during vetting, and it puts you in a listing
competing against the people you buy from.

---

## 6. Products & services entries

For directories with a structured product/service list. Ordered by catalogue
depth — the first nine are the categories carrying real stock.

```
Paints, Inks & Coatings chemicals
Food-Grade Chemicals & Additives
Solvents & Thinners
Water Treatment Chemicals
Construction Chemicals
Cleaning & Hygiene Chemicals
Adhesives & Sealants
Cosmetic & Detergent Raw Materials
Agriculture & Animal Feed Inputs
Acidity Regulators
Pigments & Fillers
Plastics & Rubber Additives
Fertiliser Inputs
Surfactants
Pulp, Paper & Packaging Chemicals
```

**Named products**, where a directory wants specific SKUs. These are high-volume
industrial commodities that buyers search by name:

```
Caustic Soda Flakes
Acetic Acid / Acetic Acid Glacial
Acetone
Aluminium Sulphate
Calcium Hypochlorite
Citric Acid
Sulphuric Acid
Hydrochloric Acid
Hydrogen Peroxide
Calcium Carbonate
Activated Carbon
Soda Ash
Boric Acid Powder
Sodium Bicarbonate
Titanium Dioxide
Bentonite Powder
Calcium Chloride
Isopropyl Alcohol
Sodium Silicate
Phosphoric Acid
```

**All twenty verified present in the live catalogue on 2026-08-07.** An earlier
draft of this list included *Sodium Hypochlorite* — Karivex does **not** stock
it, only Calcium Hypochlorite. It was removed. Re-check with the same method if
you extend the list, because listing a product you do not stock generates a
quote request you have to decline, which is worse than not being listed for it:

```
curl -s "https://karivexsolutionsltd.com/api/products/?page_size=300" \
  | python3 -c "import json,sys;print('\n'.join(sorted(p['name'] for p in json.load(sys.stdin)['results'])))"
```

**Services** (for directories separating services from products):

```
Bulk chemical distribution
Chemical procurement & sourcing
Supply chain management
Small-pack & retail chemical supply
COA & MSDS documentation with every order
Regional delivery — Kenya, Uganda, Tanzania, Rwanda
```

---

## 7. Keywords / tags field

Where a directory offers a free-text keyword box. Do not stuff these into
prose fields — they belong only in a dedicated tags input.

```
industrial chemicals Nairobi, chemical supplier Kenya, chemical distributor
Kenya, bulk chemicals Kenya, water treatment chemicals Kenya, solvents Kenya,
food grade chemicals Kenya, construction chemicals Nairobi, chemical
procurement Kenya, East Africa chemical supply
```

---

## 7a. Google Business Profile — field by field

The profile already exists. This is what belongs in each field.

**Read this first, because it decides where the effort goes.** GBP fields are
not equally weighted, and the two that matter most are the two people skip:

| Field | Effect | Effort |
|---|---|---|
| **Primary category** | The single strongest local-pack ranking factor | 2 minutes |
| **Reviews** (count, recency, replies) | Second strongest | Ongoing, free |
| Products / Services | Drives clicks to the site; weak ranking effect | An hour |
| Photos | Conversion + engagement signals | Ongoing |
| **Description** | **Not a ranking factor at all** — conversion only | 1 minute |

Getting the category right and asking ten customers for reviews will outperform
any amount of description polishing. Do those two first.

### Core fields

| Field | Value |
|---|---|
| Business name | `Karivex Solutions Ltd` — exactly. No "Nairobi", no "Chemicals" appended. Adding either is a guideline violation and risks suspension. |
| Primary category | **Chemical supplier** |
| Address | `Enterprise Road, Industrial Area, Nairobi, 00400` — keep it **visible**, do not convert to a hidden service-area business |
| Service areas | Kenya · Uganda · Tanzania · Rwanda |
| Phone (primary) | `+254 742 355548` |
| Phone (additional) | `+254 710 851911` |
| Website | `https://karivexsolutionsltd.com` — apex, https, **no trailing slash** |
| Hours | Mon–Fri 08:00–17:00 · Sat 08:00–13:00 · **Sun closed** |
| Description | § 2 above (709 chars) |

**Additional categories** — add every one that GBP offers you. Type each into
the box and take what autocompletes; Google's taxonomy is a fixed list that
changes over time, so pick from what it actually suggests rather than forcing
these strings:

- Chemical wholesaler · Distribution service · Wholesaler
- Water treatment supplier · Paint manufacturer supplier
- Industrial equipment supplier

**Do not add "Chemical manufacturer" or "Chemical plant".** Karivex
distributes. A wrong primary category is the most common cause of a business
being invisible in the local pack for the terms it should own.

### Two things to verify on the existing listing

Both are currently unconfirmed, and I cannot check them from here — Google
serves a consent wall to automated requests.

1. **That the listing is genuinely yours and claimed** — i.e. you can edit it,
   not just see it. CID `18006417983052524343`.
2. **That the Website field reads exactly `https://karivexsolutionsltd.com`.**
   This is the other half of the `sameAs` handshake: the site's JSON-LD points
   at the GBP, and the GBP has to point back. If it still carries the old
   `industrialchemicals.` subdomain, a `www.` variant, or a trailing slash, the
   two records do not connect and the strongest entity signal available is
   being wasted. This one field is worth checking before anything else.

### Products

GBP's Products section links back to the site — real referral paths, not just
decoration. Add the § 6 named products, each as its own entry:

- **Name** — the product name exactly as it appears in the catalogue
- **Category** — the catalogue category it sits under
- **Price** — leave blank / "No price". Karivex is quote-only, and a price here
  would contradict the site, which deliberately publishes none
- **Description** — first two sentences of the product page copy
- **Link** — `https://karivexsolutionsltd.com/products/<slug>`

### Services

```
Bulk chemical distribution
Chemical procurement & sourcing
Supply chain management
Small-pack & retail chemical supply
COA & MSDS documentation
Regional delivery — Kenya, Uganda, Tanzania, Rwanda
```

### Attributes

Set whichever GBP offers: onsite services, delivery, in-store pickup, wheelchair
accessibility, accepted payment methods. Only tick what is actually true — these
appear to buyers as commitments.

### Photos

Weekly-ish beats a single bulk upload; recency is an engagement signal.

- **Logo** — `https://karivexsolutionsltd.com/brand/logo-512.png`
- **Cover** — the warehouse exterior or a loading bay
- **Interior** — racking, drums, stock. This is what separates a real
  distributor from a listing that looks like a middleman
- **Products** — drums, bags, packs with visible labelling
- **Team** — staff at work

Geotagging photos is not necessary; Google strips EXIF on upload.

### Q&A

The owner may post and answer questions. Seed three or four real ones — these
are the questions the quote inbox already gets:

- *Do you supply in small quantities or bulk only?*
- *Do you provide COA and MSDS documentation?*
- *Do you deliver outside Nairobi?*
- *What is the minimum order quantity?*

### Reviews — the actual lever

The highest-value item on this page and the one that costs nothing but nerve.

- Ask after every completed delivery, while the buyer is satisfied
- Send the review link directly; do not make them search
- **Reply to every review**, positive and negative. Replies are visible and
  weighted
- Never incentivise reviews — it breaches Google's policy and the reviews get
  stripped
- A steady trickle beats twenty in one week, which reads as inorganic

For a B2B distributor, ten genuine reviews is enough to be conspicuous — most
competitors in this category have none.

---

## 8. Per-field cheat sheet

| Field a directory asks for | Paste |
|---|---|
| Business name | `Karivex Solutions Ltd` — never "Limited", never with a location suffix |
| Website | `https://karivexsolutionsltd.com` — apex, https, no trailing slash |
| Phone | `+254742355548` (E.164) or `+254 742 355548` if it rejects `+` |
| Email | `info@karivexsolutionsltd.com` |
| Address line 1 | `Enterprise Road, Industrial Area` |
| City / Postcode | `Nairobi` / `00400` |
| Tagline (≤160) | § 1 |
| GBP description | § 2 |
| Short body | § 3 |
| Full profile body | § 4 |
| Logo | `https://karivexsolutionsltd.com/brand/logo-512.png` (512×512) |

**Adding a location to the business name field** ("Karivex Solutions Ltd
Nairobi") is a GBP guideline violation and risks suspension of the listing that
is currently your only off-site property. The address field already carries the
city.

---

## Order of work

1. GBP first — it is live, and § 2 replaces whatever description is on it now.
2. LinkedIn next, using § 3. Then the URL goes into `SITE_SAME_AS` and the
   frontend gets **rebuilt** (build arg, not a restart).
3. Then Tier 1 free directories in `docs/seo-citations.md`, using § 1 and § 3.
4. Trade bodies last — they cost money and take longest to approve.

Keep a running list of where you have submitted, with the date and the live URL
once approved. Every approved profile URL is a `sameAs` candidate.
