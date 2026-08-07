"use server";
import { redirect } from "next/navigation";
import { getAdminToken, clearAdminSession } from "@/lib/admin/session";
import { adminGet, adminMutate, AdminApiError, formatDrfError } from "@/lib/admin/api";

export interface GenerationJob {
  id: number;
  status: "running" | "done" | "cancelled" | "failed";
  scope: string;
  total: number;
  processed: number;
  published: number;
  held: number;
  failed: number;
  detail: string;
  cancel_requested: boolean;
  results: Array<{
    id: number;
    name: string;
    status: "published" | "held" | "error";
    score?: number;
    errors?: string[];
    detail?: string;
  }>;
}

export interface BulkStatus {
  total: number;
  done: number;
  remaining: number;
  job: GenerationJob | null;
  categories: Array<{ id: number; name: string; total: number; done: number; remaining: number }>;
  products: Array<{
    id: number; name: string; category_id: number; category_name: string;
    done: boolean; score: number;
  }>;
}

function handle(e: unknown): { error: string } {
  if (e instanceof AdminApiError) {
    if (e.status === 401) { void clearAdminSession(); redirect("/admin/login"); }
    return { error: formatDrfError(e.body) };
  }
  throw e;
}

/** Progress snapshot. Cheap — this is what the panel polls. */
export async function bulkProgressAction(): Promise<{ status?: BulkStatus; error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  try {
    return { status: await adminGet<BulkStatus>("/ai/bulk-generate/", token) };
  } catch (e) {
    return handle(e);
  }
}

/** Starts a background run and returns immediately.
 *
 *  The generation itself does NOT happen inside this request — one product
 *  takes 30-60 seconds, and holding the connection open produced a 504 at
 *  nginx's 60-second default. This returns a job id; the panel then polls. */
export async function startGenerationAction(options: {
  productIds?: number[];
  categoryId?: number;
  onlyMissing?: boolean;
}): Promise<{ job?: GenerationJob; error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  try {
    const job = await adminMutate<GenerationJob>("/ai/bulk-generate/", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        only_missing: options.onlyMissing ?? true,
        ...(options.productIds ? { product_ids: options.productIds } : {}),
        ...(options.categoryId ? { category: options.categoryId } : {}),
      }),
    });
    return { job };
  } catch (e) {
    return handle(e);
  }
}

export async function cancelGenerationAction(): Promise<{ error?: string }> {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  try {
    await adminMutate("/ai/bulk-generate/", token, { method: "DELETE" });
    return {};
  } catch (e) {
    return handle(e);
  }
}
