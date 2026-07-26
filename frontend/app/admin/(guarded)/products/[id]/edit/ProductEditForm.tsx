"use client";
import { useActionState, useState } from "react";
import type { AdminProduct, Category, AIDraft, MediaLibraryItem } from "@/lib/admin/types";
import FaqEditor, { type Faq } from "../../../../components/FaqEditor";
import SerpPreview from "../../../../components/SerpPreview";
import OnPageSeoChecklist from "../../../../components/OnPageSeoChecklist";
import MediaLibraryPicker from "../../../../components/MediaLibraryPicker";
import { updateProductAction, regenerateDraftAction, deleteProductAction, type EditState } from "./actions";

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

      <form action={formAction} className="admin-section" encType="multipart/form-data">
        <h2>Product details</h2>
        <input type="hidden" name="faqs" value={JSON.stringify(faqs)} />
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
            <label>Appearance <input name="appearance" defaultValue={product.appearance} /></label>
            <label>Packaging <input name="packaging" defaultValue={product.packaging} /></label>
            <label>Regions <input name="regions" defaultValue={product.regions} /></label>
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
              <input type="checkbox" name="is_small_pack" value="true" defaultChecked={product.is_small_pack} /> Small-pack (Buy Now + M-Pesa)
            </label>
            <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
              <input type="checkbox" name="in_stock" value="true" defaultChecked={product.in_stock} /> In stock
            </label>
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
