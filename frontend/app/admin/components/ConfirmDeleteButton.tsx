"use client";

export default function ConfirmDeleteButton({
  action, confirmText, label = "Delete",
}: {
  action: () => Promise<void>; confirmText: string; label?: string;
}) {
  return (
    <button type="button" className="link-btn" onClick={() => { if (confirm(confirmText)) action(); }}>
      {label}
    </button>
  );
}
