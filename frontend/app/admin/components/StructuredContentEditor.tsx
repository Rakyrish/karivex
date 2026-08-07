"use client";
// Section-by-section editor for the structured content produced by the
// backend pipeline (backend/ai_tools/content_schema.py).
//
// The review step is the whole point of the pipeline: generated content is a
// proposal, and this is where a human accepts, corrects or rejects it. Two
// design choices follow from that:
//
//  * Unverified specification rows are shown, flagged, and editable rather
//    than hidden. They are the to-do list — the public page suppresses them,
//    so if staff never see them here nobody ever fills them in.
//  * "Why choose us" and "Delivery coverage" are NOT editable here. They are
//    assembled server-side from configured business data so they cannot claim
//    a credential the company lacks; making them free text would reopen
//    exactly that hole. Change them in the site settings instead.

import type { ContentSections } from "@/lib/admin/types";

const NEEDS_VERIFICATION = "Requires manual verification";

/** Applications became `{use, why}` pairs. Products generated before that hold
 *  plain strings, and staff must still be able to open and edit them — so a
 *  legacy string becomes a pair with an empty reason for them to fill in. */
function normaliseApplications(
  value: ContentSections["applications"],
): Array<{ use: string; why: string }> {
  return (value ?? []).map((item) =>
    typeof item === "string"
      ? { use: item, why: "" }
      : { use: item?.use ?? "", why: item?.why ?? "" },
  );
}

/** Line-delimited textarea <-> string[]. Keeps blank lines out of the model
 *  while still letting staff type freely mid-edit. */
function LineList({
  label, hint, value, rows = 4, onChange,
}: {
  label: string; hint?: string; value: string[]; rows?: number;
  onChange: (next: string[]) => void;
}) {
  return (
    <label>
      {label} {hint && <span className="field-hint">{hint}</span>}
      <textarea
        rows={rows}
        value={value.join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n"))}
        onBlur={(e) => onChange(e.target.value.split("\n").map((l) => l.trim()).filter(Boolean))}
      />
    </label>
  );
}

function PairList<K extends string, V extends string>({
  label, hint, value, keyName, valName, keyPlaceholder, valPlaceholder, max = 10, onChange,
}: {
  label: string; hint?: string;
  value: Array<Record<string, string>>;
  keyName: K; valName: V;
  keyPlaceholder: string; valPlaceholder: string;
  max?: number;
  onChange: (next: Array<Record<string, string>>) => void;
}) {
  const update = (i: number, field: string, val: string) =>
    onChange(value.map((row, idx) => (idx === i ? { ...row, [field]: val } : row)));

  return (
    <div>
      <span className="admin-form-section-title">{label}</span>
      {hint && <p className="field-hint">{hint}</p>}
      <div className="faq-editor">
        {value.map((row, i) => (
          <div className="faq-row" key={i}>
            <textarea
              rows={1} placeholder={keyPlaceholder}
              value={row[keyName] ?? ""}
              onChange={(e) => update(i, keyName, e.target.value)}
            />
            <textarea
              rows={2} placeholder={valPlaceholder}
              value={row[valName] ?? ""}
              onChange={(e) => update(i, valName, e.target.value)}
            />
            <button type="button" className="link-btn"
              onClick={() => onChange(value.filter((_, idx) => idx !== i))}>
              Remove
            </button>
          </div>
        ))}
        {value.length < max && (
          <button type="button" className="btn-secondary"
            onClick={() => onChange([...value, { [keyName]: "", [valName]: "" }])}>
            + Add
          </button>
        )}
      </div>
    </div>
  );
}

export default function StructuredContentEditor({
  value, onChange,
}: {
  value: ContentSections;
  onChange: (next: ContentSections) => void;
}) {
  const set = <K extends keyof ContentSections>(key: K, next: ContentSections[K]) =>
    onChange({ ...value, [key]: next });

  /** Patches one safety field. Must merge rather than replace — the SDS fields
   *  live in the same object and editing the guidance used to wipe them. */
  const setSafety = (patch: Partial<ContentSections["handling_safety"]>) =>
    set("handling_safety", {
      ...(value.handling_safety ?? { guidance: "", ppe: [] }), ...patch,
    });

  const specs = value.specifications ?? [];
  const pendingCount = specs.filter((s) => s.value === NEEDS_VERIFICATION).length;

  return (
    <div className="admin-form">
      <label>
        Product summary
        <span className="field-hint">
          Answers what it is, who buys it and where it ships — the first paragraph a buyer reads.
        </span>
        <textarea rows={6} value={value.summary ?? ""} onChange={(e) => set("summary", e.target.value)} />
      </label>

      <LineList
        label="Key features" hint="(one per line)"
        value={value.key_features ?? []} rows={6}
        onChange={(next) => set("key_features", next)}
      />

      <PairList
        label="Benefits" hint="Concrete operational advantages — not “versatile”."
        value={value.benefits ?? []}
        keyName="title" valName="detail"
        keyPlaceholder="Short label" valPlaceholder="What it saves, prevents or enables"
        max={8}
        onChange={(next) => set("benefits", next as ContentSections["benefits"])}
      />

      <div>
        <span className="admin-form-section-title">Technical specifications</span>
        <p className="field-hint">
          {pendingCount > 0
            ? `${pendingCount} value${pendingCount === 1 ? "" : "s"} still marked “${NEEDS_VERIFICATION}”. `
              + "These are hidden from the public page until filled. Take CAS number and purity "
              + "from the supplier SDS/COA — never estimate them."
            : "All values verified."}
        </p>
        <div className="faq-editor">
          {specs.map((row, i) => (
            <div className="faq-row" key={i}>
              <textarea
                rows={1} placeholder="Label"
                value={row.label}
                onChange={(e) => set("specifications", specs.map((r, idx) =>
                  idx === i ? { ...r, label: e.target.value } : r))}
              />
              <textarea
                rows={1} placeholder="Value"
                className={row.value === NEEDS_VERIFICATION ? "spec-unverified" : ""}
                value={row.value}
                onChange={(e) => set("specifications", specs.map((r, idx) =>
                  idx === i ? { ...r, value: e.target.value, verified: e.target.value.trim() !== "" && e.target.value !== NEEDS_VERIFICATION } : r))}
              />
              <button type="button" className="link-btn"
                onClick={() => set("specifications", specs.filter((_, idx) => idx !== i))}>
                Remove
              </button>
            </div>
          ))}
          <button type="button" className="btn-secondary"
            onClick={() => set("specifications", [...specs, { label: "", value: "", verified: false }])}>
            + Add specification
          </button>
        </div>
      </div>

      <LineList
        label="Available grades" hint="(one per line — only grades actually stocked)"
        value={value.available_grades ?? []} rows={3}
        onChange={(next) => set("available_grades", next)}
      />
      <LineList
        label="Packaging options" hint="(one per line — only sizes actually supplied)"
        value={value.packaging_options ?? []} rows={3}
        onChange={(next) => set("packaging_options", next)}
      />
      <label>
        Which grade is this?
        <span className="hint">
          Says which grade the listing is and what it suits, so a buyer does not order the
          wrong material off a one-item list above.
        </span>
        <textarea rows={3} value={value.grades_note ?? ""}
          onChange={(e) => set("grades_note", e.target.value)} />
      </label>

      <PairList
        label="Applications"
        hint="Each application carries WHY this chemical is the one used there — the property it contributes and what the process needs it for. A bare list of uses tells a buyer nothing they could not guess."
        value={normaliseApplications(value.applications)}
        keyName="use" valName="why"
        keyPlaceholder="The process, named precisely" valPlaceholder="Why this chemical is used there"
        max={12}
        onChange={(next) => set("applications", next as ContentSections["applications"])}
      />

      <PairList
        label="Industries served" hint="What this product does in each industry specifically."
        value={value.industries ?? []}
        keyName="name" valName="detail"
        keyPlaceholder="Industry" valPlaceholder="What it does there"
        onChange={(next) => set("industries", next as ContentSections["industries"])}
      />

      <PairList
        label="Typical industrial uses"
        hint="When is this the right choice? Factual only — describe what each chemistry is used for, never claim superiority over another product or name a competing supplier."
        value={value.typical_uses ?? []}
        keyName="scenario" valName="guidance"
        keyPlaceholder="The job the buyer is doing" valPlaceholder="Why this product suits it"
        max={6}
        onChange={(next) => set("typical_uses", next as ContentSections["typical_uses"])}
      />

      <label>
        Storage guidelines
        <textarea rows={4} value={value.storage_guidelines ?? ""}
          onChange={(e) => set("storage_guidelines", e.target.value)} />
      </label>

      <label>
        Handling &amp; safety
        <span className="field-hint">General practice only — never invent hazard codes or exposure limits.</span>
        <textarea rows={5} value={value.handling_safety?.guidance ?? ""}
          onChange={(e) => setSafety({ guidance: e.target.value })} />
      </label>
      <LineList
        label="Recommended PPE" hint="(one per line)"
        value={value.handling_safety?.ppe ?? []} rows={3}
        onChange={(next) => setSafety({ ppe: next })}
      />

      {/* SDS-only fields. The generator is told not to produce these and they
          survive a regeneration untouched, so what is typed here is the only
          thing that can ever appear on the page. Blank is the correct state
          until someone has the document open. */}
      <label>
        First aid <span className="field-hint">Copy from the supplier SDS. Leave blank if you do not have it open.</span>
        <textarea rows={3} value={value.handling_safety?.first_aid ?? ""}
          onChange={(e) => setSafety({ first_aid: e.target.value })} />
      </label>
      <label>
        Spill response <span className="field-hint">From the SDS. Containment and disposal in outline; the SDS remains the full reference.</span>
        <textarea rows={3} value={value.handling_safety?.spill_response ?? ""}
          onChange={(e) => setSafety({ spill_response: e.target.value })} />
      </label>
      <label>
        Transport <span className="field-hint">From the shipping documents — UN number, packing group, any carrier restriction.</span>
        <textarea rows={3} value={value.handling_safety?.transport ?? ""}
          onChange={(e) => setSafety({ transport: e.target.value })} />
      </label>

      <PairList
        label="FAQs" hint="Purchasing and operational questions — not what the summary already answers."
        value={value.faqs ?? []}
        keyName="q" valName="a"
        keyPlaceholder="Question" valPlaceholder="Answer"
        max={8}
        onChange={(next) => set("faqs", next as ContentSections["faqs"])}
      />

      <label>
        Call to action — headline
        <input value={value.cta?.headline ?? ""}
          onChange={(e) => set("cta", { headline: e.target.value, body: value.cta?.body ?? "" })} />
      </label>
      <label>
        Call to action — body
        <textarea rows={2} value={value.cta?.body ?? ""}
          onChange={(e) => set("cta", { headline: value.cta?.headline ?? "", body: e.target.value })} />
      </label>

      <p className="field-hint">
        “Why buy from Karivex” and “Delivery coverage” are generated from your configured
        business data rather than written here, so they can never claim a certification or
        coverage the company does not have.
      </p>
    </div>
  );
}
