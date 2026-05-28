"use client";

import { use } from "react";
import { AdminCreditAccountDetail } from "@/components/AdminCreditAccountDetail";

export default function AdminCreditAccountDetailPage({
  params,
}: {
  params: Promise<{ clientId: string }>;
}) {
  const { clientId } = use(params);
  return <AdminCreditAccountDetail clientId={Number(clientId)} />;
}
