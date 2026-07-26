"use client";

export type Faq = { q: string; a: string };

export default function FaqEditor({ value, onChange }: { value: Faq[]; onChange: (next: Faq[]) => void }) {
  function update(i: number, key: keyof Faq, val: string) {
    onChange(value.map((f, idx) => (idx === i ? { ...f, [key]: val } : f)));
  }
  function remove(i: number) {
    onChange(value.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([...value, { q: "", a: "" }]);
  }

  return (
    <div className="faq-editor">
      {value.map((faq, i) => (
        <div className="faq-row" key={i}>
          <textarea placeholder="Question" value={faq.q} onChange={(e) => update(i, "q", e.target.value)} />
          <textarea placeholder="Answer" value={faq.a} onChange={(e) => update(i, "a", e.target.value)} />
          <button type="button" className="link-btn" onClick={() => remove(i)}>Remove</button>
        </div>
      ))}
      {value.length < 7 && (
        <button type="button" className="btn-secondary" onClick={add}>+ Add FAQ</button>
      )}
    </div>
  );
}
