"""Stateless staff-session auth for the Next.js admin control center.

Reuses Django's built-in signing framework (HMAC over DJANGO_SECRET_KEY) —
no token table, no JWT library. The token is just a signed, self-expiring
reference to a User row: `TimestampSigner.sign(str(user.pk))`. This is
intentionally the SAME credential surface as Django admin (same User table,
same is_staff gate) — see dashboard/views.py LoginView, which calls
django.contrib.auth.authenticate() directly.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from rest_framework import authentication, exceptions

TOKEN_SALT = "karivex-dashboard-auth"


def make_token(user) -> str:
    return signing.TimestampSigner(salt=TOKEN_SALT).sign(str(user.pk))


class SignedTokenAuthentication(authentication.BaseAuthentication):
    """`Authorization: Bearer <token>` — see make_token() above."""
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("utf-8")
        if not header.startswith(f"{self.keyword} "):
            return None
        token = header[len(self.keyword) + 1:].strip()
        if not token:
            return None

        max_age = getattr(settings, "DASHBOARD_SESSION_HOURS", 12) * 3600
        try:
            user_pk = signing.TimestampSigner(salt=TOKEN_SALT).unsign(token, max_age=max_age)
        except signing.SignatureExpired:
            raise exceptions.AuthenticationFailed("Session expired.")
        except signing.BadSignature:
            raise exceptions.AuthenticationFailed("Invalid token.")

        User = get_user_model()
        try:
            # Re-checked at verify time (not just at login) so a demoted/deactivated
            # admin's still-unexpired token stops working immediately.
            user = User.objects.get(pk=int(user_pk), is_active=True, is_staff=True)
        except (User.DoesNotExist, ValueError):
            raise exceptions.AuthenticationFailed("Invalid token.")
        return (user, token)

    def authenticate_header(self, request):
        return self.keyword
