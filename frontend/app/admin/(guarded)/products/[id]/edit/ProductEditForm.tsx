"use client";
import { useActionState, useState } from "react";
import type {
  AdminProduct, Category, AIDraft, MediaLibraryItem,
  ContentSections, SeoAssets, StructuredContent,
} from "@/lib/admin/types";
import FaqEditor, { type Faq } from "../../../../components/FaqEditor";
import SerpPreview from "../../../../components/SerpPreview";
import OnPageSeoChecklist from "../../../../components/OnPageSeoChecklist";
import MediaLibraryPicker from "../../../../components/MediaLibraryPicker";
import StructuredContentEditor from "../../../../components/StructuredContentEditor";
import ContentQualityPanel from "../../../../components/ContentQualityPanel";
import KeywordPlanPanel from "../../../../components/KeywordPlanPanel";
import {
  updateProductAction, regenerateDraftAction, generateStructuredContentAction,
  deleteProductAction, type EditState,
} from "./actions";

const EMPTY_SECTIONS: ContentSections = {
  summary: "", key_features: [], benefits: [], specifications: [],
  available_grades: [], packaging_options: [], applications: [], industries: [],
  typical_uses: [],
  storage_guidelines: "", handling_safety: { guidance: "", ppe: [] },
  faqs: [], cta: { headline: "", body: "" },
};

const GRADES = [
  { value: "industrial", label: "Industrial / Technical" },
  { value: "food", label: "Food Grade" },
  { value: "lab", label: "Laboratory / Analytical" },
  { value: "pharma", label: "Pharmaceutical" },
  { value: "cosmetic", label: "Cosmetic Grade" },
];

const initialState: EditState = { error: null };

export default function ProductEditForm({ product, categories }: { product: AdminProduct; categories: Category[] }) {
  const boundUpdate = updateProductAction.bind(null, product.id);
  const [state, formAction, saving] = useActionState(boundUpdate, initialState);

  const [slug, setSlug] = useState(product.slug);
  const [focusKeyword, setFocusKeyword] = useState(product.focus_keyword);
  const [description, setDescription] = useState(product.description);
  const [metaTitle, setMetaTitle] = useState(product.meta_title);
  const [metaDescription, setMetaDescription] = useState(product.meta_description);
  const [applications, setApplications] = useState(product.applications);
  const [safetyInfo, setSafetyInfo] = useState(product.safety_info);
  const [imageAlt, setImageAlt] = useState(product.image_alt);
  const [faqs, setFaqs] = useState<Faq[]>(product.faqs ?? []);

  const [regenNotes, setRegenNotes] = useState("");
  const [regenSourceUrl, setRegenSourceUrl] = useState("");
  const [regenerating, setRegenerating] = useState(false);
  const [regenError, setRegenError] = useState<string | null>(null);
  const [pendingDraft, setPendingDraft] = useState<AIDraft | null>(null);

  // Structured content. Seeded from what's already saved, so opening the form
  // on a product that has never been through the pipeline shows an empty
  // editor rather than nothing at all.
  const [sections, setSections] = useState<ContentSections>(
    (product.content_sections as ContentSections)?.summary !== undefined
      ? { ...EMPTY_SECTIONS, ...(product.content_sections as ContentSections) }
      : EMPTY_SECTIONS,
  );
  const [seoAssets, setSeoAssets] = useState<SeoAssets>(product.seo_assets ?? {});
  const [structuredImageSeo, setStructuredImageSeo] = useState(product.image_seo ?? {});
  const [internalLinks, setInternalLinks] = useState(product.internal_links ?? []);
  const [generating, setGenerating] = useState(false);
  const [structuredError, setStructuredError] = useState<string | null>(null);
  const [pendingStructured, setPendingStructured] = useState<StructuredContent | null>(null);

  const report = pendingStructured?.report
    ?? ((product.content_report as StructuredContent["report"])?.metrics ? product.content_report as StructuredContent["report"] : null);

  async function handleGenerateStructured() {
    setGenerating(true);
    setStructuredError(null);
    const result = await generateStructuredContentAction(
      product.id, regenNotes, regenSourceUrl || undefined,
    );
    setGenerating(false);
    if (result.error) { setStructuredError(result.error); return; }
    if (result.content) setPendingStructured(result.content);
  }

  /** Load a generated payload into the editable fields. Still not saved —
   *  the form's own Save is what persists it. */
  function applyStructured() {
    if (!pendingStructured) return;
    setSections({ ...EMPTY_SECTIONS, ...pendingStructured.sections });
    setSeoAssets(pendingStructured.seo);
    setStructuredImageSeo(pendingStructured.image_seo);
    setInternalLinks(pendingStructured.internal_links);
    // The flat columns stay in step so the chatbot, SEO audit and any product
    // still rendering from them don't drift out of sync with the sections.
    setMetaTitle(pendingStructured.flat.meta_title);
    setMetaDescription(pendingStructured.flat.meta_description);
    setDescription(pendingStructured.flat.description);
    setApplications(pendingStructured.flat.applications);
    setSafetyInfo(pendingStructured.flat.safety_info);
    setImageAlt(pendingStructured.flat.image_alt);
    setFaqs(pendingStructured.flat.faqs);
    setPendingStructured(null);
  }

  const [imageSource, setImageSource] = useState<"upload" | "url" | "library">("upload");
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [productImageUrl, setProductImageUrl] = useState("");
  const [libraryImage, setLibraryImage] = useState<MediaLibraryItem | null>(null);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);

  async function handleRegenerate() {
    setRegenerating(true);
    setRegenError(null);
    const notes = focusKeyword
      ? `Target search phrase (work it naturally into the description, meta_title and meta_description without keyword-stuffing): "${focusKeyword}". ${regenNotes}`
      : regenNotes;
    const result = await regenerateDraftAction(product.id, notes, regenSourceUrl || undefined);
    setRegenerating(false);
    if (result.error) { setRegenError(result.error); return; }
    if (result.draft) setPendingDraft(result.draft);
  }

  function applyDraft() {
    if (!pendingDraft) return;
    setDescription(pendingDraft.description);
    setMetaTitle(pendingDraft.meta_title);
    setMetaDescription(pendingDraft.meta_description);
    setApplications(pendingDraft.applications);
    setSafetyInfo(pendingDraft.safety_info);
    setImageAlt(pendingDraft.image_alt);
    setFaqs(pendingDraft.faqs);
    setPendingDraft(null);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setUploadPreview(file ? URL.createObjectURL(file) : null);
  }

  const currentImagePreview =
    imageSource === "upload" ? (uploadPreview ?? product.image)
    : imageSource === "library" ? (libraryImage?.image || product.image)
    : (productImageUrl || product.image);

  return (
    <>
      <div className="admin-section">
        <h2>AI draft assist</h2>
        <p className="field-hint">
          {product.ai_draft_generated_at
            ? `Last generated ${new Date(product.ai_draft_generated_at).toLocaleString()}.`
            : "No AI draft generated yet."}
        </p>
        <label>Source URL <span className="field-hint">(optional — a supplier spec sheet or competitor product page, fetched server-side as grounding material)</span>
          <input value={regenSourceUrl} onChange={(e) => setRegenSourceUrl(e.target.value)} placeholder="https://…" />
        </label>
        <label>Notes for the AI <span className="field-hint">(optional — the focus keyword below is automatically included)</span>
          <textarea value={regenNotes} onChange={(e) => setRegenNotes(e.target.value)} rows={2} />
        </label>
        <div className="admin-form-actions">
          <button type="button" className="btn-secondary" disabled={regenerating} onClick={handleRegenerate}>
            {regenerating ? "Generating…" : "Regenerate AI draft"}
          </button>
          {pendingDraft && (
            <button type="button" className="cta" onClick={applyDraft}>Apply draft to fields below</button>
          )}
          {regenError && <span className="admin-form-error" role="alert">{regenError}</span>}
        </div>
      </div>

      <div className="admin-section">
        <h2>Structured content &amp; SEO</h2>
        <p className="field-hint">
          Runs the full pipeline: image analysis → sections → SEO assets → image SEO →
          FAQs → internal links → validation. Generated content is a proposal — review it
          here, then Save to publish. Nothing reaches the live page until you do.
          {product.content_generated_at
            ? ` Last generated ${new Date(product.content_generated_at).toLocaleString()}.`
            : " Never generated for this product."}
        </p>
        <div className="admin-form-actions">
          <button type="button" className="btn-secondary" disabled={generating}
            onClick={handleGenerateStructured}>
            {generating ? "Generating…" : "Generate structured content"}
          </button>
          {pendingStructured && (
            <button type="button" className="cta" onClick={applyStructured}>
              Load into the form below
            </button>
          )}
          {structuredError && <span className="admin-form-error" role="alert">{structuredError}</span>}
        </div>

        {pendingStructured && !pendingStructured.report.publishable && (
          <p className="admin-form-error" role="alert">
            This draft has blocking issues. Load it in, fix them, and the checks below will update.
          </p>
        )}
        {report?.rewritten_sections && report.rewritten_sections.length > 0 && (
          <p className="field-hint">
            Automatically rewritten to remove keyword stuffing:{" "}
            {report.rewritten_sections.join(", ")}.
          </p>
        )}
        {report && <ContentQualityPanel report={report} />}
        <KeywordPlanPanel seo={seoAssets} metrics={report?.metrics?.keywords} />
      </div>

      <form action={formAction} className="admin-section" encType="multipart/form-data">
        <h2>Product details</h2>
        <input type="hidden" name="faqs" value={JSON.stringify(faqs)} />
        {/* DRF marks HTML form input as a JSON string and parses it back into
            the JSONField — the same mechanism the faqs input above relies on. */}
        <input type="hidden" name="content_sections" value={JSON.stringify(sections.summary ? sections : {})} />
        <input type="hidden" name="seo_assets" value={JSON.stringify(seoAssets)} />
        <input type="hidden" name="image_seo" value={JSON.stringify(structuredImageSeo)} />
        <input type="hidden" name="internal_links" value={JSON.stringify(internalLinks)} />
        {imageSource === "url" && <input type="hidden" name="image_url" value={productImageUrl} />}
        {imageSource === "library" && libraryImage && (
          <input type="hidden" name="library_image_id" value={libraryImage.id} />
        )}
        <div className="admin-form">
          <div className="admin-form-grid">
            <label>Name <input name="name" defaultValue={product.name} required /></label>
            <label>
              Category
              <select name="category" defaultValue={product.category}>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>
              Grade
              <select name="grade" defaultValue={product.grade}>
                {GRADES.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            </label>
            <label>CAS number <input name="cas_number" defaultValue={product.cas_number} /></label>
            <label>Synonyms <input name="synonyms" defaultValue={product.synonyms} /></label>
            <label>Purity <input name="purity" defaultValue={product.purity} /></label>
            <label>Chemical formula <input name="chemical_formula" defaultValue={product.chemical_formula} placeholder="e.g. H2SO4" /></label>
            <label>Molecular weight <input name="molecular_weight" defaultValue={product.molecular_weight} placeholder="e.g. 98.08 g/mol" /></label>
            <label>Appearance <input name="appearance" defaultValue={product.appearance} /></label>
            <label>Packaging <input name="packaging" defaultValue={product.packaging} /></label>
            <label>Regions <input name="regions" defaultValue={product.regions} /></label>
            <label>
              Stock status
              <select name="stock_status" defaultValue={product.stock_status}>
                <option value="in_stock">In stock</option>
                <option value="low_stock">Low stock</option>
                <option value="on_request">Available on request</option>
                <option value="out_of_stock">Out of stock</option>
              </select>
            </label>
          </div>

          {/* Transport classification is deliberately separated and never
              AI-filled: these values print on shipping documents and depend on
              concentration and packing group. A wrong one is a safety and
              legal problem, not a content defect. */}
          <div className="admin-form-section-title">Transport classification — from the SDS only</div>
          <p className="field-hint">
            Leave blank unless you have read the value off the safety data sheet. Blank simply
            omits the row; a guessed UN number or hazard class can misroute a consignment.
          </p>
          <div className="admin-form-grid">
            <label>UN number <input name="un_number" defaultValue={product.un_number} placeholder="e.g. UN1830" /></label>
            <label>Hazard class <input name="hazard_class" defaultValue={product.hazard_class} placeholder="e.g. Class 8 (Corrosive)" /></label>
          </div>

          <label>URL slug <span className="field-hint">(changing this breaks any external links/bookmarks to the old URL)</span>
            <input name="slug" value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]+/g, "-"))} />
          </label>
          <label>Focus keyword <span className="field-hint">(the exact phrase buyers search for)</span>
            <input name="focus_keyword" value={focusKeyword} onChange={(e) => setFocusKeyword(e.target.value)} placeholder="e.g. caustic soda flakes kenya" />
          </label>

          <label>Description
            <textarea name="description" rows={10} value={description} onChange={(e) => setDescription(e.target.value)} required />
          </label>
          <label>
            Meta title
            <span className={`char-counter ${metaTitle.length > 70 ? "over" : ""}`}>{metaTitle.length}/70</span>
            <input name="meta_title" value={metaTitle} onChange={(e) => setMetaTitle(e.target.value)} maxLength={70} />
          </label>
          <label>
            Meta description
            <span className={`char-counter ${metaDescription.length > 160 ? "over" : ""}`}>{metaDescription.length}/160</span>
            <textarea name="meta_description" rows={2} value={metaDescription} onChange={(e) => setMetaDescription(e.target.value)} maxLength={160} />
          </label>
          <SerpPreview title={metaTitle} description={metaDescription} url={`karivex.co.ke/products/${slug}`} />

          <OnPageSeoChecklist
            focusKeyword={focusKeyword} metaTitle={metaTitle} metaDescription={metaDescription}
            description={description} slug={slug} imageAlt={imageAlt}
            faqCount={faqs.length} hasImage={Boolean(currentImagePreview)}
          />

          <label>Applications <textarea name="applications" rows={4} value={applications} onChange={(e) => setApplications(e.target.value)} /></label>
          <label>Safety info <textarea name="safety_info" rows={4} value={safetyInfo} onChange={(e) => setSafetyInfo(e.target.value)} /></label>
          <label>Image alt text <input name="image_alt" value={imageAlt} onChange={(e) => setImageAlt(e.target.value)} maxLength={160} /></label>

          <div>
            <span className="admin-form-section-title">FAQs</span>
            <FaqEditor value={faqs} onChange={setFaqs} />
          </div>

          <details className="structured-editor" open={Boolean(sections.summary)}>
            <summary className="admin-form-section-title">
              Structured page sections
              {sections.summary ? "" : " — empty, this product renders from the fields above"}
            </summary>
            <StructuredContentEditor value={sections} onChange={setSections} />
          </details>

          <div className="admin-form-section-title">Product photo</div>
          <div className="image-source-toggle">
            <label>
              <input type="radio" name="_image_source_ui" checked={imageSource === "upload"} onChange={() => setImageSource("upload")} />
              Upload from computer
            </label>
            <label>
              <input type="radio" name="_image_source_ui" checked={imageSource === "url"} onChange={() => setImageSource("url")} />
              Use an image URL
            </label>
            <label>
              <input type="radio" name="_image_source_ui" checked={imageSource === "library"} onChange={() => { setImageSource("library"); setLibraryPickerOpen(true); }} />
              Choose from library
            </label>
          </div>
          {imageSource === "upload" && (
            <>
              <input type="file" name="image" accept="image/*" onChange={handleFileChange} />
              <p className="field-hint">Leave blank to keep the current photo.</p>
            </>
          )}
          {imageSource === "url" && (
            <input
              type="text" placeholder="https://example.com/product-photo.jpg"
              value={productImageUrl} onChange={(e) => setProductImageUrl(e.target.value)}
            />
          )}
          {imageSource === "library" && (
            <button type="button" className="btn-secondary" onClick={() => setLibraryPickerOpen(true)}>
              {libraryImage ? `Selected: ${libraryImage.name} — change` : "Browse library"}
            </button>
          )}
          {currentImagePreview && <img src={currentImagePreview} alt={imageAlt} className="image-preview" />}
          {libraryPickerOpen && (
            <MediaLibraryPicker
              onClose={() => setLibraryPickerOpen(false)}
              onSelect={(item) => { setLibraryImage(item); setLibraryPickerOpen(false); }}
            />
          )}

          <div className="admin-form-section-title">Commerce</div>
          <div className="admin-form-grid">
            <label>Price (KES) <input name="price_kes" type="number" step="0.01" defaultValue={product.price_kes ?? ""} /></label>
            <label>Small-pack size <input name="small_pack_size" defaultValue={product.small_pack_size} /></label>
          </div>
          <div className="admin-form-grid">
            <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
              <input type="checkbox" name="is_small_pack" value="true" defaultChecked={product.is_small_pack} /> Small-pack size
            </label>
            {/* The in_stock checkbox was removed: the backend now derives it
                from Stock status on save, so submitting both let a stale
                checkbox silently overwrite the richer field. */}
            <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
              <input type="checkbox" name="featured" value="true" defaultChecked={product.featured} /> Featured on homepage
            </label>
          </div>

          <div className="admin-form-actions">
            <button type="submit" className="cta" disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
            {state.success && <span style={{ color: "var(--teal-500)", fontWeight: 700 }}>Saved.</span>}
            {state.error && <span className="admin-form-error" role="alert">{state.error}</span>}
            <button type="button" className="link-btn" style={{ marginLeft: "auto" }}
              onClick={() => { if (confirm(`Delete "${product.name}"? This cannot be undone.`)) deleteProductAction(product.id); }}>
              Delete product
            </button>
          </div>
        </div>
      </form>
    </>
  );
}
