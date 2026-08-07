// A real-time, Yoast/RankMath-style on-page checklist scored purely from
// what's already typed into the form — no network calls. Every check here
// targets a specific, well-established on-page ranking factor: keyword
// placement in the title/URL/first paragraph, content depth, and image alt
// text. It doesn't replace off-page factors (backlinks, domain age, Core Web
// Vitals) — those aren't controllable from a product form — but it makes the
// on-page factors that ARE controllable impossible to forget.
type Status = "pass" | "warn" | "fail";
type Check = { label: string; status: Status };

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function keywordDensity(description: string, keyword: string) {
  const words = wordCount(description);
  if (!words || !keyword) return 0;
  const re = new RegExp(`\\b${keyword.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "gi");
  const hits = (description.match(re) || []).length;
  return (hits / words) * 100;
}

export function computeSeoChecks(input: {
  focusKeyword: string;
  metaTitle: string;
  metaDescription: string;
  description: string;
  slug: string;
  imageAlt: string;
  faqCount: number;
  hasImage: boolean;
}): Check[] {
  const kw = input.focusKeyword.trim().toLowerCase();
  const checks: Check[] = [];

  if (!kw) {
    checks.push({ label: "Set a focus keyword above to unlock keyword-targeting checks", status: "fail" });
  } else {
    checks.push({
      label: `Focus keyword "${input.focusKeyword}" appears in the meta title`,
      status: input.metaTitle.toLowerCase().includes(kw) ? "pass" : "fail",
    });
    checks.push({
      label: "Focus keyword appears in the meta description",
      status: input.metaDescription.toLowerCase().includes(kw) ? "pass" : "fail",
    });
    checks.push({
      label: "Focus keyword appears in the URL slug",
      status: input.slug.toLowerCase().includes(kw.replace(/\s+/g, "-")) ? "pass" : "warn",
    });
    const firstPara = input.description.split(/\n\s*\n/)[0] ?? "";
    checks.push({
      label: "Focus keyword appears in the opening paragraph",
      status: firstPara.toLowerCase().includes(kw) ? "pass" : "warn",
    });
    const density = keywordDensity(input.description, kw);
    checks.push({
      label: `Keyword density in description (${density.toFixed(1)}% — aim for 0.5–3%)`,
      status: density >= 0.5 && density <= 3 ? "pass" : density === 0 ? "fail" : "warn",
    });
    checks.push({
      label: "Focus keyword appears in the image alt text",
      status: input.imageAlt.toLowerCase().includes(kw) ? "pass" : "warn",
    });
  }

  const words = wordCount(input.description);
  checks.push({
    label: `Description length: ${words} words (aim for 400+; long-form pages rank better)`,
    status: words >= 400 ? "pass" : words >= 250 ? "warn" : "fail",
  });

  const titleLen = input.metaTitle.length;
  checks.push({
    label: `Meta title length: ${titleLen} chars (ideal 50–60)`,
    status: titleLen >= 40 && titleLen <= 60 ? "pass" : titleLen > 0 && titleLen <= 70 ? "warn" : "fail",
  });

  const descLen = input.metaDescription.length;
  checks.push({
    label: `Meta description length: ${descLen} chars (ideal 120–155)`,
    status: descLen >= 120 && descLen <= 155 ? "pass" : descLen > 0 && descLen <= 160 ? "warn" : "fail",
  });

  checks.push({
    label: `${input.faqCount} FAQ${input.faqCount === 1 ? "" : "s"} — powers Google's FAQ rich result`,
    status: input.faqCount >= 3 ? "pass" : input.faqCount > 0 ? "warn" : "fail",
  });

  checks.push({
    label: "Product image set — required for Google Image Search and rich results",
    status: input.hasImage ? "pass" : "fail",
  });

  return checks;
}

const ICON: Record<Status, string> = { pass: "✓", warn: "!", fail: "✕" };

export default function OnPageSeoChecklist(props: Parameters<typeof computeSeoChecks>[0]) {
  const checks = computeSeoChecks(props);
  const passCount = checks.filter((c) => c.status === "pass").length;

  return (
    <div className="seo-checklist">
      <div className="seo-checklist-score">{passCount} / {checks.length} on-page checks passing</div>
      <ul className="seo-checklist-list">
        {checks.map((c, i) => (
          <li key={i} className={`seo-checklist-item seo-checklist-${c.status}`}>
            <span className="seo-checklist-icon">{ICON[c.status]}</span>
            {c.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
