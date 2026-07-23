"use client";
import { useState } from "react";

type Props = {
  productId?: number;
  productName?: string;
  mode?: "quote" | "buy";
};

export default function QuoteForm({ productId, productName, mode = "quote" }: Props) {
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("sending");
    const fd = new FormData(e.currentTarget);
    const res = await fetch("/api/proxy/quotes/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: productId, ...Object.fromEntries(fd) }),
    });
    setStatus(res.ok ? "sent" : "error");
  }

  if (status === "sent") {
    return (
      <p role="status">
        {mode === "buy" ? "Order request" : "Quote request"} received. We reply within one business hour (Mon–Sat, EAT).
      </p>
    );
  }

  const label = productName
    ? `${mode === "buy" ? "Order" : "Request a quote for"} ${productName}`
    : "Request a quote";

  return (
    <form onSubmit={submit} className="quote-form" aria-label={label}>
      <label>Name<input name="name" required /></label>
      <label>Company<input name="company" /></label>
      <label>Email<input name="email" type="email" required /></label>
      <label>Phone / WhatsApp<input name="phone" required placeholder="+2547..." /></label>
      <label>Quantity<input name="quantity" required placeholder="e.g. 10 × 25 kg bags" /></label>
      <label>Country
        <select name="country" defaultValue="Kenya">
          <option>Kenya</option><option>Uganda</option><option>Tanzania</option>
          <option>Rwanda</option><option>South Sudan</option><option>Burundi</option>
        </select>
      </label>
      <label>Message<textarea name="message" rows={3} /></label>
      <button disabled={status === "sending"}>
        {status === "sending" ? "Sending…" : mode === "buy" ? "Send order request" : "Request bulk quote"}
      </button>
      {status === "error" && <p role="alert">Something went wrong — call or WhatsApp us instead.</p>}
    </form>
  );
}
