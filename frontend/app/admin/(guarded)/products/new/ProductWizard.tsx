"use client";
import { useActionState, useEffect, useRef, useState } from "react";
import type { Category, AIDraft, MediaLibraryItem, ProductFromUrl } from "@/lib/admin/types";
import FaqEditor, { type Faq } from "../../../components/FaqEditor";
import SerpPreview, { slugPreview } from "../../../components/SerpPreview";
import OnPageSeoChecklist from "../../../components/OnPageSeoChecklist";
import MediaLibraryPicker from "../../../components/MediaLibraryPicker";
import {
  resolveImageAction, composeProductAction, createProductAction, type CreateProductState,
} from "./actions";

const GRADES = [
  { value: "industrial", label: "Industrial / Technical" },
  { value: "food", label: "Food Grade" },
  { value: "lab", label: "Laboratory / Analytical" },
  { value: "pharma", label: "Pharmaceutical" },
  { value: "cosmetic", label: "Cosmetic Grade" },
];

const initialCreateState: CreateProductState = { error: null };

type SourceMode = "url" | "upload" | "name";

/** Phase labels per source, so the wait describes what's actually happening. */
const PHASES: Record<SourceMode, string[]> = {
  url: ["Fetching the page…", "Found the product photo", "Reading the label with AI vision…",
        "Writing original copy…", "Optimising for search…"],
  upload: ["Uploading your photo…", "Reading the label with AI vision…",
           "Identifying the product…", "Writing original copy…", "Optimising for search…"],
  name: ["Looking up the product…", "Writing original copy…", "Optimising for search…"],
};

function looksLikeUrl(value: string) {
  const v = value.trim();
  if (!/^https?:\/\//i.test(v)) return false;
  try { return new URL(v).hostname.includes("."); } catch { return false; }
}

/** Loads an image URL directly in an <img>, tracking load/error state so a bad
 * URL shows a clear message rather than a broken-image icon. */
function UrlImagePreview({ url, className }: { url: string; className?: string }) {
  const [state, setState] = useState<"loading" | "loaded" | "error">("loading");
  if (!url.trim()) return null;
  return (
    <div className="url-image-preview" key={url}>
      {state === "loading" && <div className="url-image-preview-spinner" aria-hidden="true" />}
      {state === "error" && <p className="url-image-preview-error">Couldn&apos;t load an image from that URL.</p>}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt=""
        className={className ?? "image-preview"}
        style={state === "loaded" ? undefined : { position: "absolute", opacity: 0, pointerEvents: "none" }}
        onLoad={() => setState("loaded")}
        onError={() => setState("error")}
      />
    </div>
  );
}

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

  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const effectiveSlug = slugTouched ? slug : slugPreview(name);

  // ---- source stage ----
  const [sourceMode, setSourceMode] = useState<SourceMode>("url");
  const [importUrl, setImportUrl] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourcePreview, setSourcePreview] = useState<string | null>(null);
  const [sourceDragOver, setSourceDragOver] = useState(false);
  const sourceFileRef = useRef<HTMLInputElement>(null);

  const [generating, setGenerating] = useState(false);
  const [phase, setPhase] = useState(0);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [draft, setDraft] = useState<AIDraft | null>(null);
  const [confidence, setConfidence] = useState<ProductFromUrl["confidence"] | null>(null);

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
  const [uploadFileName, setUploadFileName] = useState<string | null>(null);
  const [productImageUrl, setProductImageUrl] = useState("");
  const [imageCandidates, setImageCandidates] = useState<string[]>([]);
  const [libraryImage, setLibraryImage] = useState<MediaLibraryItem | null>(null);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);

  const [createState, createFormAction, creating] = useActionState(createProductAction, initialCreateState);

  const phaseTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseCount = PHASES[sourceMode].length;
  function startPhases() {
    setPhase(0);
    phaseTimer.current = setInterval(
      () => setPhase((p) => Math.min(p + 1, phaseCount - 1)), 3200,
    );
  }
  function stopPhases() {
    if (phaseTimer.current) clearInterval(phaseTimer.current);
    phaseTimer.current = null;
  }
  useEffect(() => stopPhases, []);

  function applyResult(r: ProductFromUrl) {
    setName(r.name);
    setCategory(String(r.category_id));
    setGrade(r.grade);
    setCasNumber(r.cas_number);
    setSynonyms(r.synonyms);
    setPurity(r.purity);
    setAppearance(r.appearance);
    setPackaging(r.packaging);
    setFocusKeyword(r.focus_keyword);
    setConfidence(r.confidence);
    setDescription(r.description);
    setMetaTitle(r.meta_title);
    setMetaDescription(r.meta_description);
    setApplications(r.applications);
    setSafetyInfo(r.safety_info);
    setImageAlt(r.image_alt);
    setFaqs(r.faqs);
    setDraft(r);
  }

  /** All three source modes funnel through here. */
  async function compose(mode: SourceMode, payload: { url?: string; file?: File; name?: string }) {
    if (generating) return;
    setGenerating(true);
    setGenerateError(null);
    startPhases();

    // For a URL, resolve and show the photo first — staff see what the AI is
    // about to read while the slow drafting call runs.
    if (mode === "url" && payload.url) {
      const resolved = await resolveImageAction(payload.url);
      if (resolved.error) {
        stopPhases(); setGenerating(false); setGenerateError(resolved.error); return;
      }
      if (resolved.image_url) {
        setSourcePreview(resolved.image_url);
        setPhase((p) => Math.max(p, 1));
      }
    }

    const fd = new FormData();
    if (payload.url) fd.set("url", payload.url);
    if (payload.file) fd.set("image", payload.file);
    if (payload.name) fd.set("name", payload.name);
    if (notes.trim()) fd.set("notes", notes);

    const { result, error } = await composeProductAction(fd);
    stopPhases();
    setGenerating(false);
    if (error) { setGenerateError(error); return; }
    if (!result) return;

    // Carry the source image straight through as the product photo.
    if (mode === "upload" && payload.file) {
      setImageSource("upload");
      setUploadPreview(sourcePreview);
      setUploadFileName(payload.file.name);
    } else if (result.image_url) {
      setImageSource("url");
      setProductImageUrl(result.image_url);
      setImageCandidates(result.image_candidates ?? []);
    }
    applyResult(result);
  }

  function acceptSourceFile(file: File | undefined | null) {
    if (!file) return;
    setSourceFile(file);
    setSourcePreview(URL.createObjectURL(file));
  }

  // ---- product photo (review stage) ----
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  function putFileOnInput(input: HTMLInputElement | null, file: File) {
    if (!input) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
  }

  // The photo used for vision is also the product photo, but its <input> only
  // mounts once the review stage renders — so hand the File over on mount.
  useEffect(() => {
    if (draft && imageSource === "upload" && sourceFile && fileInputRef.current?.files?.length === 0) {
      putFileOnInput(fileInputRef.current, sourceFile);
    }
  }, [draft, imageSource, sourceFile]);

  function applyFile(file: File | undefined | null) {
    if (!file) return;
    putFileOnInput(fileInputRef.current, file);
    setSourceFile(file);
    setUploadPreview(URL.createObjectURL(file));
    setUploadFileName(file.name);
  }

  function clearUpload() {
    if (fileInputRef.current) fileInputRef.current.value = "";
    setSourceFile(null);
    setUploadPreview(null);
    setUploadFileName(null);
  }

  const previewSrc =
    imageSource === "upload" ? uploadPreview
    : imageSource === "library" ? (libraryImage?.image || null)
    : (productImageUrl || null);

  const canCompose =
    !generating && (
      sourceMode === "url" ? looksLikeUrl(importUrl)
      : sourceMode === "upload" ? Boolean(sourceFile)
      : nameInput.trim().length > 1
    );

  function runCompose() {
    if (sourceMode === "url") compose("url", { url: importUrl.trim() });
    else if (sourceMode === "upload") compose("upload", { file: sourceFile! });
    else compose("name", { name: nameInput.trim() });
  }

  return (
    <>
      {!draft && (
        <div className="ai-importer">
          <div className="ai-importer-badge">AI-powered</div>
          <h2>Create a product</h2>
          <p>
            Give the AI one thing to work from. It reads the label, identifies the
            product, and writes the full listing — specs, copy, FAQs and search
            metadata — for you to review.
          </p>

          <div className="source-mode-tabs" role="tablist">
            <button
              type="button" role="tab" aria-selected={sourceMode === "url"}
              className={sourceMode === "url" ? "is-active" : ""}
              onClick={() => setSourceMode("url")} disabled={generating}
            >
              <span aria-hidden="true">🔗</span>
              <strong>Image or page URL</strong>
              <small>Paste a link — we fetch the photo</small>
            </button>
            <button
              type="button" role="tab" aria-selected={sourceMode === "upload"}
              className={sourceMode === "upload" ? "is-active" : ""}
              onClick={() => setSourceMode("upload")} disabled={generating}
            >
              <span aria-hidden="true">📷</span>
              <strong>Upload a photo</strong>
              <small>From your computer — AI reads it</small>
            </button>
            <button
              type="button" role="tab" aria-selected={sourceMode === "name"}
              className={sourceMode === "name" ? "is-active" : ""}
              onClick={() => setSourceMode("name")} disabled={generating}
            >
              <span aria-hidden="true">✍️</span>
              <strong>Just the name</strong>
              <small>No photo or link needed</small>
            </button>
          </div>

          {sourceMode === "url" && (
            <>
              <div className={`ai-importer-field ${generating ? "is-busy" : ""}`}>
                <span className="ai-importer-icon" aria-hidden="true">🔗</span>
                <input
                  type="url" inputMode="url" value={importUrl} autoFocus disabled={generating}
                  placeholder="https://supplier.com/product-photo.jpg  —  or a product page URL"
                  onChange={(e) => setImportUrl(e.target.value)}
                  onPaste={(e) => {
                    // The input's value hasn't updated yet during paste, so
                    // read the URL off the clipboard and go straight away.
                    const pasted = e.clipboardData.getData("text").trim();
                    if (looksLikeUrl(pasted)) {
                      setImportUrl(pasted);
                      setTimeout(() => compose("url", { url: pasted }), 0);
                    }
                  }}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); runCompose(); } }}
                />
                <button type="button" className="cta" disabled={!canCompose} onClick={runCompose}>
                  {generating ? "Working…" : "Generate"}
                </button>
              </div>
              <p className="ai-importer-hint">
                Works with a direct image link or a full product page — either way the
                photo is pulled out and read.
              </p>
            </>
          )}

          {sourceMode === "upload" && (
            <div
              className={`source-dropzone ${sourceDragOver ? "is-dragover" : ""} ${sourcePreview ? "has-image" : ""}`}
              onClick={() => !generating && sourceFileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setSourceDragOver(true); }}
              onDragLeave={() => setSourceDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setSourceDragOver(false); acceptSourceFile(e.dataTransfer.files?.[0]); }}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sourceFileRef.current?.click(); } }}
              role="button" tabIndex={0}
            >
              <input
                ref={sourceFileRef} type="file" accept="image/*" className="image-dropzone-input"
                disabled={generating} onChange={(e) => acceptSourceFile(e.target.files?.[0])}
              />
              {sourcePreview ? (
                <div className="source-dropzone-preview">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={sourcePreview} alt="" />
                  <div>
                    <p className="image-dropzone-filename">{sourceFile?.name}</p>
                    <p className="field-hint">This becomes the product photo too.</p>
                    {!generating && (
                      <button
                        type="button" className="link-btn"
                        onClick={(e) => { e.stopPropagation(); setSourceFile(null); setSourcePreview(null); }}
                      >
                        Choose a different photo
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <p className="image-dropzone-hint">
                  <strong>Drag &amp; drop</strong> a product photo here, or{" "}
                  <strong>click to browse</strong> your computer.
                </p>
              )}
            </div>
          )}

          {sourceMode === "upload" && (
            <div className="ai-importer-actions">
              <button type="button" className="cta" disabled={!canCompose} onClick={runCompose}>
                {generating ? "Working…" : "✨ Read photo & generate"}
              </button>
            </div>
          )}

          {sourceMode === "name" && (
            <>
              <div className={`ai-importer-field ${generating ? "is-busy" : ""}`}>
                <span className="ai-importer-icon" aria-hidden="true">✍️</span>
                <input
                  type="text" value={nameInput} autoFocus disabled={generating}
                  placeholder="e.g. Caustic Soda Flakes"
                  onChange={(e) => setNameInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); runCompose(); } }}
                />
                <button type="button" className="cta" disabled={!canCompose} onClick={runCompose}>
                  {generating ? "Working…" : "Generate"}
                </button>
              </div>
              <p className="ai-importer-hint">
                You&apos;ll add the photo and any supplier-specific specs on the next screen.
              </p>
            </>
          )}

          <details className="ai-importer-notes">
            <summary>Add a note for the AI (optional)</summary>
            <textarea
              value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} disabled={generating}
              placeholder="e.g. we stock the 25 kg bag only; emphasise water treatment use"
            />
          </details>

          {generating && (
            <div className="ai-working">
              {sourcePreview && (
                <div className="ai-working-thumb">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={sourcePreview} alt="" />
                  <span>Reading this photo</span>
                </div>
              )}
              <ol className="ai-progress" aria-live="polite">
                {PHASES[sourceMode].map((label, i) => (
                  <li key={label} className={i < phase ? "is-done" : i === phase ? "is-active" : ""}>
                    <span className="ai-progress-dot" aria-hidden="true" />
                    {label}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {generateError && <p className="admin-form-error" role="alert">{generateError}</p>}
        </div>
      )}

      {draft && (
        <form action={createFormAction} className="wizard-step2-grid" encType="multipart/form-data">
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

          <div className="wizard-step2-main">
            <div className="review-banner">
              <div>
                <strong>Draft ready — review before publishing.</strong>
                <span>Every field below is editable. Nothing is saved until you click Create product.</span>
              </div>
              {confidence && (
                <span className={`confidence-pill confidence-${confidence}`}>{confidence} confidence</span>
              )}
            </div>

            {confidence === "low" && (
              <div className="low-confidence-note">
                The AI wasn&apos;t sure what it was looking at — check the name, CAS number
                and purity carefully before publishing.
              </div>
            )}

            <div className="admin-section">
              <h2>Product facts</h2>
              <p className="field-hint" style={{ marginTop: "-.6rem", marginBottom: "1rem" }}>
                Extracted by the AI — correct anything that looks wrong.
              </p>
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
                <label>Purity <input value={purity} onChange={(e) => setPurity(e.target.value)} /></label>
                <label>Appearance <input value={appearance} onChange={(e) => setAppearance(e.target.value)} /></label>
                <label>Packaging <input value={packaging} onChange={(e) => setPackaging(e.target.value)} /></label>
                <label>Regions served <input value={regions} onChange={(e) => setRegions(e.target.value)} /></label>
              </div>
            </div>

            <div className="admin-section">
              <h2>Content</h2>
              <div className="admin-form wide">
                <label>Description
                  <textarea name="description" rows={12} value={description} onChange={(e) => setDescription(e.target.value)} required />
                </label>
                <label>Applications <span className="field-hint">(one per line)</span>
                  <textarea name="applications" rows={4} value={applications} onChange={(e) => setApplications(e.target.value)} />
                </label>
                <label>Safety info
                  <textarea name="safety_info" rows={4} value={safetyInfo} onChange={(e) => setSafetyInfo(e.target.value)} />
                </label>
                <div>
                  <span className="admin-form-section-title">FAQs</span>
                  <FaqEditor value={faqs} onChange={setFaqs} />
                </div>
              </div>
            </div>

            <div className="admin-section">
              <h2>Product photo</h2>
              <div className="admin-form wide">
                <div className="image-source-tabs">
                  <button type="button" className={imageSource === "upload" ? "is-active" : ""} onClick={() => setImageSource("upload")}>
                    📁 Upload from computer
                  </button>
                  <button type="button" className={imageSource === "url" ? "is-active" : ""} onClick={() => setImageSource("url")}>
                    🔗 Image URL
                  </button>
                  <button
                    type="button" className={imageSource === "library" ? "is-active" : ""}
                    onClick={() => { setImageSource("library"); setLibraryPickerOpen(true); }}
                  >
                    🖼️ Choose from library
                  </button>
                </div>

                {imageSource === "upload" && (
                  <div
                    className={`image-dropzone ${dragOver ? "is-dragover" : ""}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => { e.preventDefault(); setDragOver(false); applyFile(e.dataTransfer.files?.[0]); }}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInputRef.current?.click(); } }}
                    role="button" tabIndex={0}
                  >
                    <input
                      ref={fileInputRef} type="file" name="image" accept="image/*"
                      onChange={(e) => applyFile(e.target.files?.[0])} className="image-dropzone-input"
                    />
                    {uploadPreview ? (
                      <div className="image-dropzone-preview">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={uploadPreview} alt="" className="image-preview" />
                        <div>
                          <p className="image-dropzone-filename">{uploadFileName}</p>
                          <button type="button" className="link-btn" onClick={(e) => { e.stopPropagation(); clearUpload(); }}>
                            Remove — choose a different photo
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="image-dropzone-hint">
                        <strong>Drag &amp; drop</strong> a product photo here, or <strong>click to browse</strong> your computer.
                      </p>
                    )}
                  </div>
                )}

                {imageSource === "url" && (
                  <>
                    <input
                      type="text" placeholder="https://example.com/product-photo.jpg"
                      value={productImageUrl} onChange={(e) => setProductImageUrl(e.target.value)}
                    />
                    <UrlImagePreview url={productImageUrl} />
                    {imageCandidates.length > 1 && (
                      <div className="image-candidates">
                        <span className="field-hint">Other photos found on that page:</span>
                        <div className="image-candidates-strip">
                          {imageCandidates.map((src) => (
                            <button
                              key={src} type="button"
                              className={`image-candidate ${src === productImageUrl ? "is-active" : ""}`}
                              onClick={() => setProductImageUrl(src)}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={src} alt="" loading="lazy" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}

                {imageSource === "library" && (
                  <>
                    <button type="button" className="btn-secondary" onClick={() => setLibraryPickerOpen(true)}>
                      {libraryImage ? `Selected: ${libraryImage.name} — change` : "Browse library"}
                    </button>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    {libraryImage && <img src={libraryImage.image} alt="" className="image-preview" />}
                  </>
                )}
                {libraryPickerOpen && (
                  <MediaLibraryPicker
                    onClose={() => setLibraryPickerOpen(false)}
                    onSelect={(item) => { setLibraryImage(item); setLibraryPickerOpen(false); }}
                  />
                )}

                <label>Image alt text <span className="field-hint">(what Google Images reads)</span>
                  <input name="image_alt" value={imageAlt} onChange={(e) => setImageAlt(e.target.value)} maxLength={160} />
                </label>
              </div>
            </div>

            <div className="admin-section">
              <h2>Pricing &amp; availability</h2>
              <div className="admin-form wide">
                <div className="admin-form-grid">
                  <label>Price (KES) <span className="field-hint">(leave blank for quote-only)</span>
                    <input name="price_kes" type="number" step="0.01" value={priceKes} onChange={(e) => setPriceKes(e.target.value)} />
                  </label>
                  <label>Small-pack size <input name="small_pack_size" value={smallPackSize} onChange={(e) => setSmallPackSize(e.target.value)} placeholder="e.g. 5 L" /></label>
                </div>
                <div className="admin-form-grid">
                  <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
                    <input type="checkbox" checked={isSmallPack} onChange={(e) => setIsSmallPack(e.target.checked)} /> Small-pack size
                  </label>
                  <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
                    <input type="checkbox" checked={inStock} onChange={(e) => setInStock(e.target.checked)} /> In stock
                  </label>
                  <label style={{ flexDirection: "row", alignItems: "center", display: "flex", gap: ".5rem" }}>
                    <input type="checkbox" checked={featured} onChange={(e) => setFeatured(e.target.checked)} /> Featured on homepage
                  </label>
                </div>
              </div>
            </div>
          </div>

          <aside className="admin-section wizard-step2-sidebar">
            <h2>Search optimisation</h2>
            <p className="field-hint" style={{ marginTop: "-.5rem", marginBottom: "1rem" }}>
              These fields decide where this product ranks. Aim for every check green.
            </p>
            <div className="admin-form">
              <label className="focus-keyword-field">🎯 Focus keyword
                <input value={focusKeyword} onChange={(e) => setFocusKeyword(e.target.value)} placeholder="e.g. caustic soda flakes kenya" />
              </label>
              <label>URL slug
                <input
                  value={effectiveSlug}
                  onChange={(e) => { setSlugTouched(true); setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]+/g, "-")); }}
                />
              </label>
              <label>
                Meta title
                <span className={`char-counter ${metaTitle.length > 70 ? "over" : ""}`}>{metaTitle.length}/70</span>
                <input name="meta_title" value={metaTitle} onChange={(e) => setMetaTitle(e.target.value)} maxLength={70} />
              </label>
              <label>
                Meta description
                <span className={`char-counter ${metaDescription.length > 160 ? "over" : ""}`}>{metaDescription.length}/160</span>
                <textarea name="meta_description" rows={3} value={metaDescription} onChange={(e) => setMetaDescription(e.target.value)} maxLength={160} />
              </label>
              <SerpPreview title={metaTitle} description={metaDescription} url={`karivex.co.ke/products/${effectiveSlug}`} />
              <OnPageSeoChecklist
                focusKeyword={focusKeyword} metaTitle={metaTitle} metaDescription={metaDescription}
                description={description} slug={effectiveSlug} imageAlt={imageAlt}
                faqCount={faqs.length} hasImage={Boolean(previewSrc)}
              />
              <div className="admin-form-actions">
                <button type="submit" className="cta" disabled={creating}>{creating ? "Creating…" : "Create product"}</button>
              </div>
              {createState.error && <span className="admin-form-error" role="alert">{createState.error}</span>}
            </div>
          </aside>
        </form>
      )}
    </>
  );
}
