from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """Two-level catalogue taxonomy.

    Top level (parent=None) is the INDUSTRY a buyer works in — Water
    Treatment, Food & Beverage, Paints & Coatings. Second level is the
    chemical function within it — Coagulants & Flocculants, Preservatives,
    Solvents. Buyers search by the industry they're in ("water treatment
    chemicals kenya") far more than by chemical family, so the industry
    level is what earns the landing pages; the function level narrows a
    large catalogue without competing for the same query.

    Deliberately a plain self-FK rather than a tree library: two levels is
    the whole requirement, and this keeps the query for a mega-menu to one
    prefetch.
    """
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="children",
        help_text="Leave empty for a top-level industry. Set it to nest this "
                  "as a chemical-function sub-category of that industry.",
    )
    # Menus read better curated than alphabetical; ties fall back to name.
    display_order = models.IntegerField(
        default=0, help_text="Lower numbers appear first in menus."
    )
    # Industry tiles on the homepage are image-led. Optional: the tile falls
    # back to a themed gradient so an industry without a photo still looks
    # designed rather than broken.
    image = models.ImageField(
        upload_to="categories/", blank=True, null=True,
        help_text="Tile/banner image for this category. Landscape (approx 4:3) works best.",
    )
    image_alt = models.CharField(
        max_length=160, blank=True,
        help_text="Describes the image for search engines and screen readers.",
    )
    # SEO
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["display_order", "name"]

    @property
    def is_industry(self) -> bool:
        return self.parent_id is None

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.meta_title:
            # Target 60 chars, not the field's 70. Google truncates the SERP
            # title at roughly 60 and audit tools flag anything longer, so the
            # extra 10 were only ever rendered as an ellipsis. Drop to
            # progressively shorter framings rather than hard-truncating, which
            # would cut mid-word — a long name like "Antiscalants & Corrosion
            # Inhibitors" overflows every form but the bare name.
            suffix = " | Karivex"
            for base in (
                f"{self.name} Suppliers in Kenya & East Africa",
                f"{self.name} Suppliers in Kenya",
                f"{self.name} Kenya",
                self.name,
            ):
                if len(base) + len(suffix) <= 60:
                    self.meta_title = base + suffix
                    break
            else:
                self.meta_title = self.name[:60]
        if self.image and not self.image_alt:
            self.image_alt = f"{self.name} supplied by Karivex Solutions, Nairobi"[:160]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent.name} → {self.name}" if self.parent_id else self.name


class Product(models.Model):
    GRADE_CHOICES = [
        ("industrial", "Industrial / Technical"),
        ("food", "Food Grade"),
        ("lab", "Laboratory / Analytical"),
        ("pharma", "Pharmaceutical"),
        ("cosmetic", "Cosmetic Grade"),
    ]

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    # Spec table — mirrors what competitors show, but structured (they use flat HTML)
    cas_number = models.CharField(max_length=30, blank=True)
    synonyms = models.CharField(max_length=300, blank=True)
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES, default="industrial")
    purity = models.CharField(max_length=60, blank=True, help_text="e.g. ≥98%")
    appearance = models.CharField(max_length=200, blank=True)
    packaging = models.CharField(max_length=200, blank=True, help_text="e.g. 25 kg bags, 200 L drums")

    # Technical identifiers buyers search and order against. Blank means "not
    # verified" — the spec table shows a verification marker rather than a
    # value, and the public page omits the row entirely. Never populate these
    # by inference; take them from the supplier's SDS or COA.
    chemical_formula = models.CharField(
        max_length=120, blank=True, help_text="e.g. H2SO4. Leave blank if unverified.")
    molecular_weight = models.CharField(
        max_length=60, blank=True, help_text="e.g. 98.08 g/mol. Leave blank if unverified.")
    density = models.CharField(
        max_length=60, blank=True,
        help_text="e.g. 1.83 g/cm³. For solutions this varies with concentration — "
                  "check it matches the grade you actually supply.")
    # UN number and hazard class are TRANSPORT CLASSIFICATION, not chemistry.
    # They depend on concentration and packing group, they appear on shipping
    # documents, and a wrong value is a legal and safety problem rather than an
    # SEO one. They are therefore staff-entered only — ai_tools never writes
    # them, exactly like cas_number and purity.
    # Where cas_number / chemical_formula / molecular_weight came from when
    # they were filled by lookup rather than typed in: PubChem CID, the URL,
    # the name that matched, and every CAS PubChem lists for it. Kept so a
    # reviewer can check a value instead of trusting it, and so a bad match can
    # be traced back to the name that produced it. Empty for staff-entered
    # values — those need no citation.
    identifier_source = models.JSONField(default=dict, blank=True)
    un_number = models.CharField(
        max_length=20, blank=True,
        help_text="e.g. UN1830. Transport classification — read it off the SDS, never estimate.")
    # GHS terms kept distinct because they are distinct things, and conflating
    # them on a chemical supply page reads as not knowing the vocabulary.
    signal_word = models.CharField(
        max_length=20, blank=True, help_text='GHS signal word — "Danger" or "Warning".')
    hazard_statements = models.JSONField(
        default=list, blank=True,
        help_text='H-codes with their text, e.g. ["H314: Causes severe skin burns and eye damage"].')
    hazard_class = models.CharField(
        max_length=120, blank=True,
        help_text="GHS hazard class, e.g. Skin corrosion/irritation. NOT the signal word "
                  "and NOT an H-code — those are separate fields above.")

    # Content — MUST be unique per product. Do not template-generate; this is the
    # duplicate-content trap all four competitors fell into.
    description = models.TextField(help_text="Unique, human-written. 250+ words.")
    applications = models.TextField(blank=True, help_text="One application per line.")
    safety_info = models.TextField(blank=True)
    faqs = models.JSONField(default=list, blank=True,
                            help_text='[{"q": "...", "a": "..."}] — rendered as FAQPage schema')

    # Commerce
    is_small_pack = models.BooleanField(default=False, help_text="Sold in small-pack sizes. All products are quote-only.")
    price_kes = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                    help_text="Small-pack retail price. Leave blank for quote-only.")
    small_pack_size = models.CharField(max_length=60, blank=True, help_text="e.g. 5 L, 1 kg")
    # Four states rather than a boolean: "In stock" and "Out of stock" cannot
    # express the two cases that actually describe most of this catalogue —
    # thin stock worth flagging, and items brought in per order. `in_stock` is
    # kept and auto-synced in save() because the API, the chatbot context and
    # the storefront filters all read it; this field is the detail layer on top.
    STOCK_STATUS = [
        ("in_stock", "In stock"),
        ("low_stock", "Low stock"),
        ("on_request", "Available on request"),
        ("out_of_stock", "Out of stock"),
    ]
    stock_status = models.CharField(max_length=20, choices=STOCK_STATUS, default="in_stock")
    in_stock = models.BooleanField(
        default=True,
        help_text="Derived from Stock status on save — edit that field instead.")
    featured = models.BooleanField(default=False, help_text="Show in homepage featured section.")

    # SEO
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    focus_keyword = models.CharField(max_length=100, blank=True,
                                     help_text="Primary search phrase this product should rank for, "
                                               "e.g. 'caustic soda flakes kenya' — drives the on-page SEO "
                                               "checklist in the admin control center.")
    regions = models.CharField(max_length=200,
                               default="Kenya, Uganda, Tanzania, Rwanda",
                               help_text="Comma-separated, used in title/schema areaServed")

    image = models.ImageField(upload_to="products/", blank=True, null=True)
    image_alt = models.CharField(max_length=160, blank=True)

    # AI-assisted drafting (see ai_tools app). Always a suggestion for staff to
    # review and copy into the fields above — never written to the live fields
    # automatically. Keeps the "unique, human-reviewed" guarantee above intact.
    ai_draft = models.JSONField(default=dict, blank=True)
    ai_draft_generated_at = models.DateTimeField(null=True, blank=True)

    # --- Structured content (ai_tools.services.generate_structured_product_content)
    #
    # Published, human-reviewed structured sections — distinct from `ai_draft`,
    # which stays a pending suggestion. Additive on purpose: the flat
    # `description`/`applications`/`safety_info`/`faqs` fields above remain the
    # source of truth for every product generated before this existed, and the
    # renderer falls back to them whenever `content_sections` is empty. That
    # keeps the existing catalogue rendering unchanged with no bulk
    # regeneration and no risk to content that already reads well.
    content_sections = models.JSONField(
        default=dict, blank=True,
        help_text="Structured page sections (summary, features, benefits, specs, "
                  "industries, FAQs…). Empty means this product renders from the "
                  "flat description fields above.",
    )
    seo_assets = models.JSONField(
        default=dict, blank=True,
        help_text="Keyword groups, heading outline, canonical path, Open Graph "
                  "and Twitter metadata.",
    )
    image_seo = models.JSONField(
        default=dict, blank=True,
        help_text="Image alt, title, caption and suggested file name.",
    )
    internal_links = models.JSONField(
        default=list, blank=True,
        help_text="Suggested internal links, resolved against real routes only.",
    )
    # 0-100 on-page completeness, from ai_tools.validation.score_content. An
    # eligibility/hygiene measure, NOT a ranking prediction — structured data
    # and on-page tidiness are not ranking factors.
    seo_score = models.PositiveSmallIntegerField(default=0)
    content_report = models.JSONField(
        default=dict, blank=True,
        help_text="Validation issues and metrics from the last generation.",
    )
    content_generated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    @property
    def has_structured_content(self) -> bool:
        """True once the structured pipeline has produced a summary for this
        product. The renderer keys section-based layout off this."""
        return bool((self.content_sections or {}).get("summary"))

    @property
    def pending_verification(self) -> list[str]:
        """Spec labels still carrying the verification marker. Surfaced in the
        admin list so the CAS/purity backlog is visible where it is fixed,
        rather than only in a management command."""
        from ai_tools.content_schema import needs_verification

        return [row.get("label", "") for row in (self.content_sections or {}).get("specifications", [])
                if needs_verification(row.get("value"))]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # Keep the legacy boolean in step with the richer status. Low stock is
        # still stock: a buyer can order it today, so it must not disappear
        # from "in stock" listings.
        self.in_stock = self.stock_status in {"in_stock", "low_stock"}
        if not self.meta_title:
            # 60-char budget: "Buy Caustic Soda Flakes in Kenya | Karivex"
            self.meta_title = f"Buy {self.name} in Kenya | Karivex"[:70]
        if not self.image_alt:
            self.image_alt = f"{self.name} — {self.packaging or 'industrial packaging'} supplied by Karivex Solutions, Nairobi"[:160]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class GenerationJob(models.Model):
    """A bulk content-generation run, executed in the background.

    Exists because generating one product takes 30-60 seconds and an HTTP
    request must not be held open that long. The admin previously drove the
    run synchronously and hit a 504 at nginx's 60-second default
    `proxy_read_timeout` — the work had already been done and paid for, and
    the response was discarded.

    So the request now creates one of these, starts a worker thread and
    returns immediately; the browser polls this row for progress. Because
    per-product completion is recorded on Product itself, a job that dies
    mid-run (worker recycled, container restarted) loses nothing — starting a
    new one simply picks up whatever is still outstanding.
    """
    STATUS = [
        ("running", "Running"),
        ("done", "Finished"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
    ]
    status = models.CharField(max_length=12, choices=STATUS, default="running")
    # Snapshot of what the run was asked to do, for the audit trail.
    scope = models.CharField(max_length=200, blank=True)
    product_ids = models.JSONField(default=list, blank=True)

    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    published = models.PositiveIntegerField(default=0)
    held = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    # Most recent first, capped — this is a progress feed, not an archive.
    results = models.JSONField(default=list, blank=True)
    detail = models.TextField(blank=True)

    # Set by the admin to stop the run; the worker checks it between products
    # so a stop never interrupts a product mid-generation.
    cancel_requested = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self) -> bool:
        return self.status == "running"

    def __str__(self):
        return f"{self.get_status_display()} — {self.processed}/{self.total}"


class BlogPost(models.Model):
    """Buyer-intent long-tail content — must be unique, human-written. Never
    template-generated (see Product.description docstring: same trap)."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, help_text="Shown in list view and used as meta_description fallback.")
    body = models.TextField(help_text="Markdown. Rendered server-side on the frontend.")
    cover_image = models.ImageField(upload_to="blog/", blank=True, null=True)
    cover_image_alt = models.CharField(max_length=160, blank=True)
    related_products = models.ManyToManyField(Product, blank=True, related_name="related_posts")

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.meta_title:
            self.meta_title = self.title[:70]
        if not self.meta_description:
            self.meta_description = self.excerpt[:160]
        if not self.cover_image_alt and self.cover_image:
            self.cover_image_alt = f"{self.title} — Karivex Solutions"[:160]
        if self.published and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class QuoteRequest(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes",
                                help_text="Optional — blank for general inquiries not tied to one product.")
    name = models.CharField(max_length=120)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    quantity = models.CharField(max_length=120, help_text="e.g. 10 x 25kg bags")
    country = models.CharField(max_length=60, default="Kenya")
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.product} ({self.created_at:%Y-%m-%d})"


class Order(models.Model):
    """An order placed off-site and recorded by staff.

    Karivex does not take payment on the website — every product is quote-only
    and payment is settled off-platform. The M-Pesa/Daraja fields that used to
    sit here were scaffolding for an STK-push flow that was never built, and
    were dropped once that direction was abandoned.
    """
    STATUS = [("pending", "Pending"), ("paid", "Paid"), ("delivered", "Delivered"), ("cancelled", "Cancelled")]
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    amount_kes = models.DecimalField(max_digits=12, decimal_places=2)
    customer_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, help_text="Contact number, e.g. 2547XXXXXXXX")
    delivery_address = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
