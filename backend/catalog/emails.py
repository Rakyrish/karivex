"""
Transactional email via Resend's HTTP API.

Why Resend directly over Django's email backend: the domain's DKIM key is
already published at resend._domainkey.karivexsolutionsltd.com and the custom
MAIL FROM is send.karivexsolutionsltd.com, so Resend is the sender that is
actually authorised to use this domain. Going through SMTP would mean a second
credential and a second authorisation path for no benefit.

Same degrade-gracefully contract as the OpenAI and Cloudinary config in
settings.py: a blank RESEND_API_KEY disables sending, loudly in the log and
silently to the customer. Nothing in here may ever raise into a request — a
quote that reaches the database but fails to notify is a problem to fix in the
logs, whereas a quote lost because the mail provider was down is lost revenue.
"""
import html
import logging
import threading

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
TIMEOUT = 10


def _post(payload: dict) -> bool:
    """One Resend call. Returns success; never raises."""
    if not settings.RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY is blank — quote notification not sent (to=%s subject=%r). "
            "Set it in .env to enable.", payload.get("to"), payload.get("subject"),
        )
        return False
    try:
        r = requests.post(
            RESEND_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            timeout=TIMEOUT,
        )
        if r.status_code >= 400:
            # Resend returns a JSON body explaining the rejection (unverified
            # domain, bad From, invalid recipient). Log it verbatim — guessing
            # at these from a bare status code wastes hours.
            logger.error("Resend rejected %r: %s %s", payload.get("subject"), r.status_code, r.text[:500])
            return False
        # Log the provider-side id on success too. Without it a delivered quote
        # and a silently-dropped one look identical in the logs, and the id is
        # what you paste into Resend's dashboard to trace a specific message.
        try:
            msg_id = r.json().get("id", "?")
        except ValueError:
            msg_id = "?"
        logger.info("Resend accepted %r -> id=%s to=%s", payload.get("subject"), msg_id, payload.get("to"))
        return True
    except requests.RequestException as exc:
        logger.error("Resend call failed for %r: %s", payload.get("subject"), exc)
        return False


def _rows(quote) -> list[tuple[str, str]]:
    product = quote.product.name if quote.product else "General enquiry (no specific product)"
    return [
        ("Product", product),
        ("Quantity", quote.quantity),
        ("Name", quote.name),
        ("Company", quote.company or "—"),
        ("Email", quote.email),
        ("Phone", quote.phone),
        ("Country", quote.country),
        ("Message", quote.message or "—"),
        ("Received", quote.created_at.strftime("%d %b %Y, %H:%M")),
    ]


def _internal_email(quote) -> dict:
    rows = _rows(quote)
    # Every value here is customer-supplied, so it is escaped before it goes
    # anywhere near an HTML body.
    table = "".join(
        f'<tr><td style="padding:6px 14px 6px 0;color:#3f4e5c;vertical-align:top;white-space:nowrap">{html.escape(k)}</td>'
        f'<td style="padding:6px 0;color:#0a1830"><strong>{html.escape(str(v))}</strong></td></tr>'
        for k, v in rows
    )
    product = quote.product.name if quote.product else "General enquiry"
    return {
        "from": settings.QUOTE_FROM_EMAIL,
        "to": settings.QUOTE_NOTIFY_TO,
        # Staff hit Reply and land in the customer's inbox, not ours.
        "reply_to": quote.email,
        "subject": f"Quote request: {product} — {quote.name}"
                   + (f" ({quote.company})" if quote.company else ""),
        "html": (
            '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:640px">'
            f'<h2 style="color:#0a1830;margin:0 0 4px">New quote request</h2>'
            f'<p style="color:#3f4e5c;margin:0 0 18px">via {html.escape(settings.SITE["name"])}</p>'
            f'<table style="border-collapse:collapse;font-size:15px">{table}</table>'
            '<p style="color:#3f4e5c;font-size:13px;margin-top:22px">'
            'Reply to this email to answer the customer directly.</p></div>'
        ),
        "text": "New quote request\n\n" + "\n".join(f"{k}: {v}" for k, v in rows),
    }


def _customer_ack(quote) -> dict:
    site = settings.SITE
    product = quote.product.name if quote.product else "your enquiry"
    return {
        "from": settings.QUOTE_FROM_EMAIL,
        "to": [quote.email],
        "reply_to": site["email"],
        "subject": f"We've received your quote request — {site['name']}",
        "html": (
            '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:640px">'
            f'<p>Hi {html.escape(quote.name.split(" ")[0])},</p>'
            f'<p>Thanks for your enquiry about <strong>{html.escape(product)}</strong> '
            f'(quantity: {html.escape(quote.quantity)}). A member of our team will come back to you '
            'with pricing and lead time within one business hour during working hours '
            f'({html.escape(site["hours"])}).</p>'
            f'<p>Every consignment ships with {html.escape(site["certifications"].lower())}. '
            f'{html.escape(site["delivery_nairobi"])}; {html.escape(site["delivery_regional"].lower())}.</p>'
            f'<p>If it is urgent, call or WhatsApp us on '
            f'<a href="tel:{html.escape(site["phone"])}">{html.escape(site["phone"])}</a>.</p>'
            f'<p style="color:#3f4e5c">— {html.escape(site["name"])}</p></div>'
        ),
        "text": (
            f"Hi {quote.name.split(' ')[0]},\n\n"
            f"Thanks for your enquiry about {product} (quantity: {quote.quantity}). "
            f"We'll come back to you with pricing and lead time within one business hour "
            f"during working hours ({site['hours']}).\n\n"
            f"Urgent? Call or WhatsApp {site['phone']}.\n\n— {site['name']}"
        ),
    }


def _send_all(quote) -> None:
    _post(_internal_email(quote))
    # The acknowledgement is best-effort and secondary: a bounced or mistyped
    # customer address must never stop the internal notification, which is the
    # one that actually protects the sale. Ordered accordingly.
    if settings.QUOTE_SEND_CUSTOMER_ACK:
        _post(_customer_ack(quote))


def send_quote_emails(quote) -> None:
    """
    Fire-and-forget. Runs on a daemon thread so a slow or unreachable Resend
    never adds latency to the customer's form submission — the revalidation
    webhook in signals.py can afford to block because it runs on admin saves,
    but this one sits directly in a conversion path.
    """
    threading.Thread(target=_send_all, args=(quote,), daemon=True).start()
