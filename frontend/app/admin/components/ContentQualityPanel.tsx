"use client";
// Renders the validation report from backend/ai_tools/validation.py.
//
// The score is on-page completeness, not a ranking prediction — the copy below
// says so on purpose. Structured data and on-page hygiene decide whether a
// page is *eligible* for rich results and whether a crawler understands it;
// they are not ranking factors, and presenting the number as "how well this
// will rank" would set an expectation the work cannot meet.

import type { ContentReport } from "@/lib/admin/types";

const SEVERITY_LABEL = { error: "Blocking", warning: "Review" } as const;

export default function ContentQualityPanel({ report }: { report: ContentReport }) {
  const { score, publishable, issues, metrics } = report;
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  const band = score >= 80 ? "pass" : score >= 55 ? "warn" : "fail";

  return (
    <div className="seo-checklist">
      <div className="seo-checklist-score">
        {score} / 100 on-page completeness
        <span className={`quality-band quality-${band}`}>
          {publishable ? "Ready to publish" : `${errors.length} blocking issue${errors.length === 1 ? "" : "s"}`}
        </span>
      </div>

      <p className="field-hint">
        {metrics.word_count} words · {metrics.faq_count} FAQs ·{" "}
        {Math.round(metrics.repetition_ratio * 100)}% repeated phrasing ·{" "}
        {metrics.sections_present}/{metrics.sections_required} sections complete
        {metrics.pending_verification.length > 0 && (
          <> · {metrics.pending_verification.length} spec{metrics.pending_verification.length === 1 ? "" : "s"} unverified</>
        )}
      </p>

      <ul className="seo-checklist-list">
        {[...errors, ...warnings].map((issue, i) => (
          <li key={i} className={`seo-checklist-item seo-checklist-${issue.severity === "error" ? "fail" : "warn"}`}>
            <span className="seo-checklist-icon">{issue.severity === "error" ? "✕" : "!"}</span>
            <strong>{SEVERITY_LABEL[issue.severity]}</strong> — {issue.message}
          </li>
        ))}
        {issues.length === 0 && (
          <li className="seo-checklist-item seo-checklist-pass">
            <span className="seo-checklist-icon">✓</span>
            No issues found.
          </li>
        )}
      </ul>

      <p className="field-hint">
        Measures whether this page is complete and machine-readable — not how it will rank.
        Unverified specifications are a warning by design: an honest gap is safer than a
        guessed CAS number or purity figure.
      </p>
    </div>
  );
}
