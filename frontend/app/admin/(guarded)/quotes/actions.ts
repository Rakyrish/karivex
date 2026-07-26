"use server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { getAdminToken } from "@/lib/admin/session";
import { adminMutate } from "@/lib/admin/api";

export async function toggleHandledAction(id: number, handled: boolean) {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  await adminMutate(`/dashboard/quotes/${id}/`, token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handled }),
  });
  revalidatePath("/admin/quotes");
}
