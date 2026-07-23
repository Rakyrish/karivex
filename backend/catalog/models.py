from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """e.g. Water Treatment, Solvents & Thinners, Construction Chemicals."""
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    # SEO
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.meta_title:
            self.meta_title = f"{self.name} Suppliers in Kenya & East Africa | Karivex"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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

    # Content — MUST be unique per product. Do not template-generate; this is the
    # duplicate-content trap all four competitors fell into.
    description = models.TextField(help_text="Unique, human-written. 250+ words.")
    applications = models.TextField(blank=True, help_text="One application per line.")
    safety_info = models.TextField(blank=True)
    faqs = models.JSONField(default=list, blank=True,
                            help_text='[{"q": "...", "a": "..."}] — rendered as FAQPage schema')

    # Commerce
    is_small_pack = models.BooleanField(default=False, help_text="If true: Buy Now + M-Pesa. Else: quote only.")
    price_kes = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                    help_text="Small-pack retail price. Leave blank for quote-only.")
    small_pack_size = models.CharField(max_length=60, blank=True, help_text="e.g. 5 L, 1 kg")
    in_stock = models.BooleanField(default=True)
    featured = models.BooleanField(default=False, help_text="Show in homepage featured section.")

    # SEO
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    regions = models.CharField(max_length=200,
                               default="Kenya, Uganda, Tanzania, Rwanda",
                               help_text="Comma-separated, used in title/schema areaServed")

    image = models.ImageField(upload_to="products/", blank=True, null=True)
    image_alt = models.CharField(max_length=160, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.meta_title:
            # 60-char budget: "Buy Caustic Soda Flakes in Kenya | Karivex"
            self.meta_title = f"Buy {self.name} in Kenya | Karivex"[:70]
        if not self.image_alt:
            self.image_alt = f"{self.name} — {self.packaging or 'industrial packaging'} supplied by Karivex Solutions, Nairobi"[:160]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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
    """Small-pack M-Pesa orders. STK push via Daraja API — wired in milestone 3."""
    STATUS = [("pending", "Pending"), ("paid", "Paid"), ("delivered", "Delivered"), ("cancelled", "Cancelled")]
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    amount_kes = models.DecimalField(max_digits=12, decimal_places=2)
    customer_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, help_text="M-Pesa number, 2547XXXXXXXX")
    delivery_address = models.TextField()
    mpesa_checkout_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
