"use client";
import { useState, useRef, useEffect } from "react";

type Role = "user" | "assistant";
type Source = { type: "product" | "post"; slug: string; title: string };
type Message = { role: Role; content: string; sources?: Source[] };

export default function ChatWidget({ phone, whatsapp }: { phone: string; whatsapp: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, open]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setSending(true);

    try {
      const res = await fetch("/api/proxy/ai/chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });
      if (!res.ok) {
        setUnavailable(true);
        setMessages((m) => [
          ...m,
          { role: "assistant", content: `Chat isn't available right now — call or WhatsApp us at ${phone}.` },
        ]);
        return;
      }
      const data = await res.json();
      setMessages((m) => [...m, { role: "assistant", content: data.answer, sources: data.sources }]);
    } catch {
      setUnavailable(true);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `Chat isn't available right now — call or WhatsApp us at ${phone}.` },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-widget">
      {open && (
        <div className="chat-panel" role="dialog" aria-label="Chat with Karivex">
          <div className="chat-panel-header">
            <span>Ask Karivex</span>
            <button type="button" aria-label="Close chat" onClick={() => setOpen(false)}>
              &times;
            </button>
          </div>
          <div className="chat-panel-body" ref={listRef}>
            {messages.length === 0 && (
              <p className="chat-empty">
                Ask about products, specs, delivery or pricing. For urgent orders,{" "}
                <a href={`https://wa.me/${whatsapp.replace(/[^\d]/g, "")}`}>WhatsApp us</a> directly.
              </p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble chat-bubble-${m.role}`}>
                <p>{m.content}</p>
                {m.sources && m.sources.length > 0 && (
                  <ul className="chat-sources">
                    {m.sources.map((s) => (
                      <li key={`${s.type}-${s.slug}`}>
                        <a href={s.type === "product" ? `/products/${s.slug}` : `/blog/${s.slug}`}>{s.title}</a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {sending && <div className="chat-bubble chat-bubble-assistant chat-typing">Thinking&hellip;</div>}
          </div>
          <form className="chat-panel-form" onSubmit={send}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…"
              disabled={unavailable}
              aria-label="Your question"
            />
            <button type="submit" disabled={sending || unavailable || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      )}
      <button
        type="button"
        className="chat-fab"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? "Close" : "Chat"}
      </button>
    </div>
  );
}
