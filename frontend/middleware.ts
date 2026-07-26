import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin/constants";

// Cheap presence-only check — the authoritative check is Django's
// IsAdminUser + SignedTokenAuthentication on every real API call, re-verified
// again by app/admin/(guarded)/layout.tsx's own auth/me/ call on every page
// load. This just fast-rejects the obviously-logged-out case.
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname === "/admin/login") return NextResponse.next();
  if (!request.cookies.has(ADMIN_SESSION_COOKIE)) {
    const url = new URL("/admin/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/admin/:path*"] };
