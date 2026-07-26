"use server";
import { redirect } from "next/navigation";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminGet, AdminApiError } from "@/lib/admin/api";
import type { MediaLibraryItem } from "@/lib/admin/types";

export async function getMediaLibraryAction(q?: string): Promise<{ items?: MediaLibraryItem[]; error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");

  const query = q?.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
  try {
    const items = await adminGet<MediaLibraryItem[]>(`/dashboard/media-library/${query}`, token);
    return { items };
  } catch (e) {
    if (e instanceof AdminApiError) {
      if (e.status === 401) { await clearAdminSession(); redirect("/admin/login"); }
      return { error: "Could not load the image library." };
    }
    throw e;
  }
}
