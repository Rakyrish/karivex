from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html, format_html_join, linebreaks

from ai_tools import services as ai_services
from .models import Category, Product, BlogPost, QuoteRequest, Order


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "grade", "purity", "is_small_pack", "price_kes", "in_stock", "featured"]
    list_filter = ["category", "grade", "is_small_pack", "in_stock", "featured"]
    search_fields = ["name", "cas_number", "synonyms"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["ai_draft_preview"]
    actions = ["generate_ai_draft", "suggest_internal_links_action"]
    fieldsets = [
        (None, {"fields": ["category", "name", "slug", "image", "image_alt"]}),
        ("Specifications", {"fields": ["cas_number", "synonyms", "grade", "purity", "appearance", "packaging"]}),
        ("Content (unique per product — no templates)", {"fields": ["description", "applications", "safety_info", "faqs"]}),
        ("Commerce", {"fields": ["is_small_pack", "price_kes", "small_pack_size", "in_stock", "featured"]}),
        ("SEO", {"fields": ["meta_title", "meta_description", "regions"]}),
        ("AI assist — draft only, review before saving", {"fields": ["ai_draft_preview"]}),
    ]

    @admin.display(description="AI draft preview")
    def ai_draft_preview(self, obj):
        draft = obj.ai_draft or {}
        if not draft:
            return "No AI draft yet — select this product in the list view and run the " \
                   "“Generate AI content draft” action."
        faqs_html = format_html_join(
            "", "<li><strong>{}</strong><br>{}</li>",
            ((f.get("q", ""), f.get("a", "")) for f in draft.get("faqs", [])),
        )
        return format_html(
            "<div style='max-width:640px'>"
            "<p><strong>Meta title</strong> ({} chars): {}</p>"
            "<p><strong>Meta description</strong> ({} chars): {}</p>"
            "<p><strong>Description:</strong>{}</p>"
            "<p><strong>Applications:</strong>{}</p>"
            "<p><strong>Safety info:</strong>{}</p>"
            "<p><strong>Image alt:</strong> {}</p>"
            "<p><strong>FAQs:</strong></p><ul>{}</ul>"
            "<p><em>Generated {}. Draft only — copy what you want into the fields above, then Save.</em></p>"
            "</div>",
            len(draft.get("meta_title", "")), draft.get("meta_title", ""),
            len(draft.get("meta_description", "")), draft.get("meta_description", ""),
            linebreaks(draft.get("description", "")),
            linebreaks(draft.get("applications", "")),
            linebreaks(draft.get("safety_info", "")),
            draft.get("image_alt", ""),
            faqs_html or "—",
            obj.ai_draft_generated_at or "never",
        )

    @admin.action(description="Generate AI content draft (OpenAI)")
    def generate_ai_draft(self, request, queryset):
        generated = 0
        for product in queryset:
            try:
                draft = ai_services.generate_product_draft(product)
            except ai_services.AIConfigError:
                self.message_user(
                    request, "OPENAI_API_KEY is not set — add it to .env to use this feature.",
                    level=messages.ERROR,
                )
                return
            except Exception as exc:
                self.message_user(request, f"Failed to generate draft for {product.name}: {exc}", level=messages.WARNING)
                continue
            Product.objects.filter(pk=product.pk).update(ai_draft=draft, ai_draft_generated_at=timezone.now())
            generated += 1
        if generated:
            self.message_user(
                request, f"Generated AI draft for {generated} product(s). Open each product to review before publishing.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Suggest internal links")
    def suggest_internal_links_action(self, request, queryset):
        for product in queryset:
            suggestions = ai_services.suggest_internal_links(product)
            if suggestions:
                text = "; ".join(f"{s['title']} ({s['type']})" for s in suggestions)
                self.message_user(request, f"{product.name}: {text}", level=messages.INFO)
            else:
                self.message_user(request, f"{product.name}: no related content found.", level=messages.INFO)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ["title", "published", "published_at", "updated_at"]
    list_filter = ["published"]
    search_fields = ["title", "excerpt", "body"]
    prepopulated_fields = {"slug": ["title"]}
    filter_horizontal = ["related_products"]
    fieldsets = [
        (None, {"fields": ["title", "slug", "excerpt", "body", "cover_image", "cover_image_alt"]}),
        ("Internal linking", {"fields": ["related_products"]}),
        ("SEO", {"fields": ["meta_title", "meta_description"]}),
        ("Publishing", {"fields": ["published", "published_at"]}),
    ]


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ["name", "product", "quantity", "country", "created_at", "handled"]
    list_filter = ["handled", "country"]
    list_editable = ["handled"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["product", "customer_name", "amount_kes", "status", "created_at"]
    list_filter = ["status"]
