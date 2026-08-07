import { type PhoneLine, dialable, formatPhone } from "@/lib/site";

type Props = {
  /** Every published line, primary first. */
  phones: PhoneLine[];
  email: string;
  whatsapp: string;
  hours: string;
  regions: string[];
};

export default function TopBar({ phones, email, whatsapp, hours, regions }: Props) {
  return (
    <div className="top-bar">
      <div className="top-bar-inner">
        <div className="top-bar-contact">
          {/* The handset icon renders once, against the first number only.
              Repeating it per line reads as two unrelated contact methods
              rather than two numbers for the same thing — and at 14px the
              second icon is pure noise. The `aria-label` carries the role so
              a screen reader hears "Sales (alt)" rather than a bare number
              that sounds like a repeat of the previous link. */}
          {phones.map((line, i) => (
            <a
              key={line.number}
              href={`tel:${dialable(line.number)}`}
              aria-label={`Call ${line.label}: ${formatPhone(line.number)}`}
              className={line.primary ? undefined : "top-bar-phone-alt"}
            >
              {i === 0 && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
              )}
              {formatPhone(line.number)}
            </a>
          ))}
          <a href={`https://wa.me/${whatsapp.replace(/[^\d]/g, "")}`} className="top-bar-whatsapp">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12.04 2c-5.46 0-9.9 4.44-9.9 9.9 0 1.75.46 3.45 1.32 4.95L2 22l5.29-1.39a9.9 9.9 0 0 0 4.75 1.21h.01c5.46 0 9.9-4.44 9.9-9.9 0-2.64-1.03-5.13-2.9-6.99A9.82 9.82 0 0 0 12.04 2z" />
            </svg>
            WhatsApp
          </a>
          <a href={`mailto:${email}`} className="top-bar-email">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="m22 6-10 7L2 6" />
            </svg>
            {email}
          </a>
        </div>
        <div className="top-bar-meta">
          <span>{hours}</span>
          <span aria-hidden="true">&middot;</span>
          <span>Serving {regions.join(", ")}</span>
        </div>
      </div>
    </div>
  );
}
