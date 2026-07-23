from django.contrib import admin
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
    fieldsets = [
        (None, {"fields": ["category", "name", "slug", "image", "image_alt"]}),
        ("Specifications", {"fields": ["cas_number", "synonyms", "grade", "purity", "appearance", "packaging"]}),
        ("Content (unique per product — no templates)", {"fields": ["description", "applications", "safety_info", "faqs"]}),
        ("Commerce", {"fields": ["is_small_pack", "price_kes", "small_pack_size", "in_stock", "featured"]}),
        ("SEO", {"fields": ["meta_title", "meta_description", "regions"]}),
    ]


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
