"use client";
// Bulk regeneration of structured content.
//
// The run happens on the SERVER, not in this component. Starting it returns a
// job id immediately and this panel then polls for progress. That is the whole
// design point: one product takes 30-60 seconds, and the earlier version —
// which held an HTTP request open for a batch — died at nginx's 60-second
// default `proxy_read_timeout` with a 504, after the OpenAI calls had already
// completed and been paid for.
//
// Because the work is server-side, closing this tab does not stop the run, and
// reopening the page reattaches to it.
//
// Publishing rules match the single-product path: only content that passes
// validation goes live, the rest is parked as a draft. Bulk is not a way
// around the gate.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  bulkProgressAction, startGenerationAction, cancelGenerationAction,
  type BulkStatus, type GenerationJob,
} from "./actions";

type Mode = "remaining" | "category" | "selected";

const POLL_MS = 4000;

export default function BulkGeneratePanel() {
  const [status, setStatus] = useState<BulkStatus | null>(null);
  const [mode, setMode] = useState<Mode>("remaining");
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const job: GenerationJob | null = status?.job ?? null;
  const running = job?.status === "running";

  const refresh = useCallback(async () => {
    const result = await bulkProgressAction();
    if (result.status) setStatus(result.status);
    if (result.error) setError(result.error);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Poll only while something is running — an idle admin page should not sit
  // hitting the API every few seconds forever.
  useEffect(() => {
    if (!running) return;
    timer.current = setTimeout(() => { void refresh(); }, POLL_MS);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [running, job?.processed, refresh]);

  const products = status?.products ?? [];
  const visibleProducts = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? products.filter((p) => p.name.toLowerCase().includes(q)) : products;
  }, [products, filter]);

  function toggle(id: number) {
    setSelected((previous) => {
      const next = new Set(previous);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function start() {
    setStarting(true);
    setError(null);
    const result = await startGenerationAction({
      productIds: mode === "selected" ? [...selected] : undefined,
      categoryId: mode === "category" ? categoryId ?? undefined : undefined,
      onlyMissing: mode !== "selected",
    });
    setStarting(false);
    if (result.error) { setError(result.error); return; }
    await refresh();
  }

  async function stop() {
    await cancelGenerationAction();
    await refresh();
  }

  const chosenCategory = status?.categories.find((c) => c.id === categoryId);
  const runnable =
    mode === "remaining" ? (status?.remaining ?? 0) > 0
    : mode === "category" ? (chosenCategory?.remaining ?? 0) > 0
    : selected.size > 0;

  const overallPct = status?.total ? Math.round((status.done / status.total) * 100) : 0;
  const jobPct = job?.total ? Math.round((job.processed / job.total) * 100) : 0;

  const startLabel = starting ? "Starting…"
    : mode === "remaining" ? `Generate remaining ${status?.remaining ?? 0}`
    : mode === "category" ? `Generate ${chosenCategory?.remaining ?? 0} in ${chosenCategory?.name ?? "category"}`
    : `Generate ${selected.size} selected`;

  return (
    <div className="admin-section">
      <h2>Regenerate product content</h2>
      <p className="field-hint">
        Runs the full pipeline — identifier lookup, sections, SEO assets, image SEO, internal
        links, validation. Products that pass are published; anything that fails is saved as a
        draft for review. Existing descriptions and FAQs are never overwritten.
      </p>

      {status && (
        <>
          <div className="bulk-progress" role="progressbar" aria-valuenow={overallPct}
               aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${overallPct}%` }} />
          </div>
          <p className="bulk-progress-label">
            <strong>{status.done} regenerated</strong> · <strong>{status.remaining} not yet</strong>
            {" "}· {status.total} products total ({overallPct}%)
          </p>
        </>
      )}

      {job && job.status !== "done" && (
        <div className={`bulk-job bulk-job-${job.status}`}>
          <strong>
            {job.status === "running" && `Running — ${job.processed} of ${job.total} (${jobPct}%)`}
            {job.status === "cancelled" && `Stopped after ${job.processed} of ${job.total}`}
            {job.status === "failed" && "Run failed"}
          </strong>
          <span>
            {job.published} published · {job.held} held{job.failed > 0 && <> · {job.failed} failed</>}
          </span>
          {job.detail && <span className="admin-form-error">{job.detail}</span>}
        </div>
      )}

      {running && (
        <p className="field-hint">
          This runs on the server — you can close this page and come back. Progress updates every
          few seconds.
        </p>
      )}

      <fieldset className="bulk-modes" disabled={running}>
        {([
          ["remaining", "All remaining"],
          ["category", "By category"],
          ["selected", "Pick products"],
        ] as Array<[Mode, string]>).map(([value, label]) => (
          <label key={value}>
            <input type="radio" name="bulk-mode" checked={mode === value}
                   onChange={() => setMode(value)} />
            {label}
          </label>
        ))}
      </fieldset>

      {mode === "category" && status && (
        <label className="bulk-category">
          Category
          <select value={categoryId ?? ""} disabled={running}
                  onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Choose an industry…</option>
            {status.categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} — {c.done}/{c.total} done, {c.remaining} remaining
              </option>
            ))}
          </select>
        </label>
      )}

      {mode === "selected" && status && (
        <div className="bulk-picker">
          <div className="bulk-picker-head">
            <input type="search" value={filter} placeholder="Filter products…"
                   onChange={(e) => setFilter(e.target.value)} disabled={running} />
            <span className="field-hint">{selected.size} selected</span>
            <button type="button" className="link-btn" disabled={running}
                    onClick={() => setSelected(new Set(visibleProducts.filter((p) => !p.done).map((p) => p.id)))}>
              Select all not-yet-regenerated
            </button>
            <button type="button" className="link-btn" disabled={running}
                    onClick={() => setSelected(new Set())}>Clear</button>
          </div>
          <ul className="bulk-picker-list">
            {visibleProducts.map((p) => (
              <li key={p.id}>
                <label>
                  <input type="checkbox" checked={selected.has(p.id)} disabled={running}
                         onChange={() => toggle(p.id)} />
                  <span className="bulk-picker-name">{p.name}</span>
                  <span className={`bulk-badge ${p.done ? "is-done" : "is-pending"}`}>
                    {p.done ? `done · ${p.score}` : "not regenerated"}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="admin-form-actions">
        {!running && (
          <button type="button" className="cta" disabled={starting || !runnable} onClick={start}>
            {startLabel}
          </button>
        )}
        {running && (
          <button type="button" className="btn-secondary" onClick={stop}
                  disabled={job?.cancel_requested}>
            {job?.cancel_requested ? "Stopping after this product…" : "Stop after this product"}
          </button>
        )}
        <button type="button" className="link-btn" onClick={() => void refresh()}>Refresh</button>
        {error && <span className="admin-form-error" role="alert">{error}</span>}
      </div>

      {job && job.results.length > 0 && (
        <ul className="bulk-results">
          {job.results.map((row, i) => (
            <li key={`${row.id}-${i}`} className={`bulk-${row.status}`}>
              <Link href={`/admin/products/${row.id}/edit`}>{row.name}</Link>
              {row.status === "published" && <span>published · score {row.score}</span>}
              {row.status === "held" && (
                <span title={row.errors?.join(" | ")}>
                  held — {row.errors?.[0] ?? "failed validation"}
                </span>
              )}
              {row.status === "error" && <span>error — {row.detail}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
