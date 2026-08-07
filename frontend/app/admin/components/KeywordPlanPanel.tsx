"use client";
// The per-product keyword strategy, as actually applied.
//
// Shows the primary keyword's placement across the surfaces that matter and
// the final keyword groups. Two deliberate framing choices:
//
//  * The slug row is informational, never a failure. Renaming a live URL to
//    fit a keyword costs every inbound link and bookmark pointing at it —
//    a worse trade than the marginal gain, so the backend reports it and
//    stops there.
//  * Groups are shown with their counts against the target minimum, because
//    "12 secondary keywords" is meaningful and "has secondary keywords" is not.

import type { KeywordMetrics, SeoAssets } from "@/lib/admin/types";

const GROUPS: Array<{ key: keyof SeoAssets; label: string; min: number }> = [
  { key: "secondary_keywords", label: "Secondary", min: 10 },
  { key: "semantic_keywords", label: "Semantic", min: 6 },
  { key: "long_tail_keywords", label: "Long-tail", min: 4 },
  { key: "buyer_intent_keywords", label: "Buyer intent", min: 4 },
  { key: "geographic_keywords", label: "Geographic", min: 4 },
];

const PLACEMENT_LABELS: Array<{ key: keyof KeywordMetrics["placement"]; label: string }> = [
  { key: "meta_title", label: "SEO title" },
  { key: "h1", label: "H1 heading" },
  { key: "first_100_words", label: "First 100 words" },
  { key: "meta_description", label: "Meta description" },
  { key: "summary", label: "Product summary" },
  { key: "cta", label: "Call to action" },
  { key: "slug", label: "URL slug" },
];

export default function KeywordPlanPanel({
  seo, metrics,
}: {
  seo: SeoAssets;
  metrics?: KeywordMetrics | Record<string, never>;
}) {
  const placement = (metrics as KeywordMetrics)?.placement;
  const stuffed = (metrics as KeywordMetrics)?.stuffed_sections ?? [];
  const density = (metrics as KeywordMetrics)?.section_density ?? {};
  const primary = seo.focus_keyword || (metrics as KeywordMetrics)?.primary_keyword || "";

  if (!primary) return null;

  return (
    <div className="seo-checklist keyword-panel">
      <div className="seo-checklist-score">
        Primary keyword: <span className="keyword-primary">{primary}</span>
      </div>

      {placement && (
        <ul className="seo-checklist-list">
          {PLACEMENT_LABELS.map(({ key, label }) => {
            const ok = placement[key];
            // The slug is advisory: a miss here is not worth breaking URLs over.
            const status = ok ? "pass" : key === "slug" ? "warn" : "warn";
            return (
              <li key={key} className={`seo-checklist-item seo-checklist-${status}`}>
                <span className="seo-checklist-icon">{ok ? "✓" : "!"}</span>
                {label}
                {key === "slug" && !ok && (
                  <span className="field-hint"> — left as-is on purpose; renaming breaks existing links</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {stuffed.length > 0 && (
        <p className="admin-form-error">
          Over-optimised after rewriting: {stuffed.join(", ")}. Thin the repetition by hand.
        </p>
      )}

      <div className="keyword-groups">
        {GROUPS.map(({ key, label, min }) => {
          const items = (seo[key] as string[] | undefined) ?? [];
          return (
            <details key={key} className="keyword-group">
              <summary>
                {label}{" "}
                <span className={items.length >= min ? "keyword-count-ok" : "keyword-count-low"}>
                  {items.length}
                </span>
                <span className="field-hint"> / {min} min</span>
              </summary>
              {items.length > 0 ? (
                <ul className="keyword-chips">
                  {items.map((k) => (
                    <li key={k}>{k}</li>
                  ))}
                </ul>
              ) : (
                <p className="field-hint">None generated.</p>
              )}
            </details>
          );
        })}
      </div>

      {Object.keys(density).length > 0 && (
        <p className="field-hint">
          Keyword density by section:{" "}
          {Object.entries(density)
            .map(([section, value]) => `${section} ${value}%`)
            .join(" · ")}
        </p>
      )}
    </div>
  );
}
