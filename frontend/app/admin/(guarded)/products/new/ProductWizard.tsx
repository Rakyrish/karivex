"use client";
import { useActionState, useState } from "react";
import type { Category, AIDraft, MediaLibraryItem } from "@/lib/admin/types";
import FaqEditor, { type Faq } from "../../../components/FaqEditor";
import SerpPreview, { slugPreview } from "../../../components/SerpPreview";
import OnPageSeoChecklist from "../../../components/OnPageSeoChecklist";
import MediaLibraryPicker from "../../../components/MediaLibraryPicker";
import { generateDraftAction, createProductAction, type CreateProductState } from "./actions";

const GRADES = [
  { value: "industrial", label: "Industrial / Technical" },
  { value: "food", label: "Food Grade" },
  { value: "lab", label: "Laboratory / Analytical" },
  { value: "pharma", label: "Pharmaceutical" },
  { value: "cosmetic", label: "Cosmetic Grade" },
];

const initialCreateState: CreateProductState = { error: null };

export default function ProductWizard({ categories }: { categories: Category[] }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState(categories[0]?.id.toString() ?? "");
  const [grade, setGrade] = useState("industrial");
  const [casNumber, setCasNumber] = useState("");
  const [synonyms, setSynonyms] = useState("");
  const [purity, setPurity] = useState("");
  const [appearance, setAppearance] = useState("");
  const [packaging, setPackaging] = useState("");
  const [regions, setRegions] = useState("Kenya, Uganda, Tanzania, Rwanda");
  const [focusKeyword, setFocusKeyword] = useState("");
  const [notes, setNotes] = useState("");
  const [referenceImageUrl, setReferenceImageUrl] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");

  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const effectiveSlug = slugTouched ? slug : slugPreview(name);

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [draft, setDraft] = useState<AIDraft | null>(null);

  const [description, setDescription] = useState("");
  const [metaTitle, setMetaTitle] = useState("");
  const [metaDescription, setMetaDescription] = useState("");
  const [applications, setApplications] = useState("");
  const [safetyInfo, setSafetyInfo] = useState("");
  const [imageAlt, setImageAlt] = useState("");
  const [faqs, setFaqs] = useState<Faq[]>([]);

  const [priceKes, setPriceKes] = useState("");
  const [isSmallPack, setIsSmallPack] = useState(false);
  const [smallPackSize, setSmallPackSize] = useState("");
  const [inStock, setInStock] = useState(true);
  const [featured, setFeatured] = useState(false);

  const [imageSource, setImageSource] = useState<"upload" | "url" | "library">("upload");
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [productImageUrl, setProductImageUrl] = useState("");
  const [libraryImage, setLibraryImage] = useState<MediaLibraryItem | null>(null);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);

  const [createState, createFormAction, creating] = useActionState(createProductAction, initialCreateState);

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    const result = await generateDraftAction({
      name, category, grade, cas_number: casNumber, synonyms, purity, appearance,
      packaging, regions, focus_keyword: focusKeyword, notes, image_url: referenceImageUrl || undefined,
      source_url: sourceUrl || undefined,
    });
    setGenerating(false);
    if (result.error) { setGenerateError(result.error); return; }
    if (result.draft) {
      setDraft(result.draft);
      setDescription(result.draft.description);
      setMetaTitle(result.draft.meta_title);
      setMetaDescription(result.draft.meta_description);
      setApplications(result.draft.applications);
      setSafetyInfo(result.draft.safety_info);
      setImageAlt(result.draft.image_alt);
      setFaqs(result.draft.faqs);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setUploadPreview(file ? URL.createObjectURL(file) : null);
  }

  const canGenerate = name.trim().length > 0 && category !== "" && !generating;
  const previewSrc =
    imageSource === "upload" ? uploadPreview
    : imageSource === "library" ? (libraryImage?.image || null)
    : (productImageUrl || null);

  return (
    <>
      <div className="admin-section">
        <h2>1. Product facts</h2>
        <div className="admin-form-grid">
          <label>Name <input value={name} onChange={(e) => setName(e.target.value)} required /></label>
          <label>
            Category
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>
            Grade
            <select value={grade} onChange={(e) => setGrade(e.target.value)}>
              {GRADES.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
          </label>
          <label>CAS number <input value={casNumber} onChange={(e) => setCasNumber(e.target.value)} /></label>
          <label>Synonyms <input value={synonyms} onChange={(e) => setSynonyms(e.target.value)} /></label>
          <label>Purity <input value={purity} onChange={(e) => setPurity(e.target.value)} placeholder="e.g. ≥98%" /></label>
          <label>Appearance <input value={appearance} onChange={(e) => setAppearance(e.target.value)} /></label>
          <label>Packaging <input value={packaging} onChange={(e) => setPackaging(e.target.value)} placeholder="e.g. 25 kg bags" /></label>
          <label>Regions served <input value={regions} onChange={(e) => setRegions(e.target.value)} /></label>
          <label>Reference image URL <span className="field-hint">(optional — helps the AI describe appearance, not saved as the product photo)</span>
            <input value={referenceImageUrl} onChange={(e) => setReferenceImageUrl(e.target.value)} placeholder="https://…" />
          </label>
        </div>
        <label style={{ marginTop: "1rem" }}>
          Focus keyword <span className="field-hint">(the exact phrase buyers search — e.g. "caustic soda flakes kenya". Drives the on-page checklist below and the AI draft.)</span>
          <input value={focusKeyword} onChange={(e) => setFocusKeyword(e.target.value)} placeholder="e.g. caustic soda flakes kenya" />
        </label>
        <label style={{ marginTop: "1rem" }}>
          Source URL <span className="field-hint">(optional — a supplier spec sheet or competitor product page. Fetched server-side and used as grounding material; the AI still rewrites everything in its own words.)</span>
          <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://…" />
        </label>
        <label style={{ marginTop: "1rem" }}>
          Staff notes for the AI <span className="field-hint">(optional)</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
        </label>
        <div className="admin-form-actions">
          <button type="button" className="cta" disabled={!canGenerate} onClick={handleGenerate}>
            {generating ? "Generating…" : draft ? "Regenerate with AI" : "Generate with AI"}
          </button>
          {generateError && <span className="admin-form-error" role="alert">{generateError}</span>}
        </div>
      </div>

      {draft && (
        <form action={createFormAction} className="admin-section" encType="multipart/form-data">
          <h2>2. Review &amp; publish</h2>
          <input type="hidden" name="name" value={name} />
          <input type="hidden" name="slug" value={effectiveSlug} />
          <input type="hidden" name="category" value={category} />
          <input type="hidden" name="grade" value={grade} />
          <input type="hidden" name="cas_number" value={casNumber} />
          <input type="hidden" name="synonyms" value={synonyms} />
          <input type="hidden" name="purity" value={purity} />
          <input type="hidden" name="appearance" value={appearance} />
          <input type="hidden" name="packaging" value={packaging} />
          <input type="hidden" name="regions" value={regions} />
          <input type="hidden" name="focus_keyword" value={focusKeyword} />
          <input type="hidden" name="faqs" value={JSON.stringify(faqs)} />
          <input type="hidden" name="is_small_pack" value={isSmallPack ? "true" : "false"} />
          <input type="hidden" name="in_stock" value={inStock ? "true" : "false"} />
          <input type="hidden" name="featured" value={featured ? "true" : "false"} />
          {imageSource === "url" && <input type="hidden" name="image_url" value={productImageUrl} />}
          {imageSource === "library" && libraryImage && (
            <input type="hidden" name="library_image_id" value={libraryImage.id} />
          )}

          <div className="admin-form">
            <label>URL slug <span className="field-hint">(shown in the address bar and in Google — include the region/keyword competitors bake into theirs)</span>
              <input
                value={effectiveSlug}
                onChange={(e) => { setSlugTouched(true); setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]+/g, "-")); }}
              />
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
            <SerpPreview title={metaTitle} description={metaDescription} url={`karivex.co.ke/products/${effectiveSlug}`} />

            <OnPageSeoChecklist
              focusKeyword={focusKeyword} metaTitle={metaTitle} metaDescription={metaDescription}
              description={description} slug={effectiveSlug} imageAlt={imageAlt}
              faqCount={faqs.length} hasImage={Boolean(previewSrc)}
            />

            <label>Applications <span className="field-hint">(one per line)</span>
              <textarea name="applications" rows={4} value={applications} onChange={(e) => setApplications(e.target.value)} />
            </label>
            <label>Safety info
              <textarea name="safety_info" rows={4} value={safetyInfo} onChange={(e) => setSafetyInfo(e.target.value)} />
            </label>
            <label>Image alt text
              <input name="image_alt" value={imageAlt} onChange={(e) => setImageAlt(e.target.value)} maxLength={160} />
            </label>

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
              <input type="file" name="image" accept="image/*" onChange={handleFileChange} />
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
            {previewSrc && <img src={previewSrc} alt="" className="image-preview" />}
            {libraryPickerOpen && (
              <MediaLibraryPicker
                onClose={() => setLibraryPickerOpen(false)}
                onSelect={(item) => { setLibraryImage(item); setLibraryPickerOpen(false); }}
              />
            )}

            <div className="admin-form-grid" style={{ marginTop: "1rem" }}>
              <label>Price (KES) <span className="field-hint">(leave blank for quote-only)</span>
                <input name="price_kes" type="number" step="0.01" value={priceKes} onChange={(e) => setPriceKes(e.target.value)} />
              </label>
              <label>Small-pack size <input name="small_pack_size" value={smallPackSize} onChange={(e) => setSmallPackSize(e.target.value)} placeholder="e.g. 5 L" /></label>
            </div>
            <div className="admin-form-grid">
              <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
                <input type="checkbox" checked={isSmallPack} onChange={(e) => setIsSmallPack(e.target.checked)} /> Small-pack (Buy Now + M-Pesa)
              </label>
              <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
                <input type="checkbox" checked={inStock} onChange={(e) => setInStock(e.target.checked)} /> In stock
              </label>
              <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
                <input type="checkbox" checked={featured} onChange={(e) => setFeatured(e.target.checked)} /> Featured on homepage
              </label>
            </div>

            <div className="admin-form-actions">
              <button type="submit" className="cta" disabled={creating}>{creating ? "Creating…" : "Create product"}</button>
              {createState.error && <span className="admin-form-error" role="alert">{createState.error}</span>}
            </div>
          </div>
        </form>
      )}
    </>
  );
}
