"use server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { getAdminToken } from "@/lib/admin/session";
import { adminMutate } from "@/lib/admin/api";

export async function updateOrderStatusAction(id: number, formData: FormData) {
  const token = await getAdminToken();
  if (!token) redirect("/admin/login");
  await adminMutate(`/dashboard/orders/${id}/`, token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: formData.get("status") }),
  });
  revalidatePath("/admin/orders");
}
