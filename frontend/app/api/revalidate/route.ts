import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

// Django post_save signal posts here. Same webhook pattern as your other sites.
export async function POST(req: NextRequest) {
  const body = await req.json();
  if (body.secret !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }
  const paths: string[] = Array.isArray(body.paths) ? body.paths : [];
  paths.forEach((p) => revalidatePath(p));
  return NextResponse.json({ ok: true, revalidated: paths });
}
