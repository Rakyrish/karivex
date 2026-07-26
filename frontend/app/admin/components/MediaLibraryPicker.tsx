"use client";
import { useEffect, useState } from "react";
import type { MediaLibraryItem } from "@/lib/admin/types";
import { getMediaLibraryAction } from "../(guarded)/products/media-library-actions";

export default function MediaLibraryPicker({
  onSelect,
  onClose,
}: {
  onSelect: (item: MediaLibraryItem) => void;
  onClose: () => void;
}) {
  const [items, setItems] = useState<MediaLibraryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  async function load(query: string) {
    setError(null);
    const result = await getMediaLibraryAction(query);
    if (result.error) { setError(result.error); return; }
    setItems(result.items ?? []);
  }

  useEffect(() => { load(""); }, []);

  return (
    <div className="media-library-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="media-library-modal" onClick={(e) => e.stopPropagation()}>
        <div className="media-library-header">
          <h3>Choose from library</h3>
          <button type="button" className="link-btn" onClick={onClose}>Close</button>
        </div>
        <input
          type="text"
          placeholder="Search by product name…"
          value={q}
          onChange={(e) => { setQ(e.target.value); load(e.target.value); }}
          style={{ marginBottom: "1rem" }}
        />
        {error && <p className="admin-form-error" role="alert">{error}</p>}
        {!error && items === null && <p className="field-hint">Loading…</p>}
        {items && items.length === 0 && <p className="field-hint">No uploaded product photos yet.</p>}
        {items && items.length > 0 && (
          <div className="media-library-grid">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                className="media-library-item"
                onClick={() => onSelect(item)}
                title={item.name}
              >
                <img src={item.image} alt={item.image_alt || item.name} />
                <span>{item.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
