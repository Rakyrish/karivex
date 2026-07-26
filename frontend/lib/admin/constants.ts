// No "server-only" import here on purpose — middleware.ts runs on the Edge
// runtime and can't pull in next/headers-dependent modules; this file has to
// stay importable from both the Edge middleware and the Node-runtime
// lib/admin/session.ts.
export const ADMIN_SESSION_COOKIE = "karivex_admin_session";
