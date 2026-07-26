// Cosmetic only — a real slug is computed server-side by Product.save()
// (django.utils.text.slugify), which this approximation may not exactly match.
export function slugPreview(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "product-name";
}

export default function SerpPreview({
  title, description, url,
}: {
  title: string; description: string; url: string;
}) {
  return (
    <div className="serp-preview">
      <p className="serp-preview-url">{url}</p>
      <p className="serp-preview-title">{title || "Untitled product — Karivex"}</p>
      <p className="serp-preview-desc">{description || "No meta description yet — search engines will pick an excerpt from the page instead."}</p>
    </div>
  );
}
