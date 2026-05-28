"use client";

import { Typography } from "@mui/material";
import { useTranslations } from "next-intl";
import { AdminCreditAccounts } from "@/components/AdminCreditAccounts";

export default function AdminCreditAccountsPage() {
  const t = useTranslations("admin.creditAccounts");
  return (
    <>
      <Typography variant="h5" gutterBottom>
        {t("title")}
      </Typography>
      <AdminCreditAccounts />
    </>
  );
}
