"use client";

import { Typography } from "@mui/material";
import { useTranslations } from "next-intl";
import { AdminPrinterSettings } from "@/components/AdminPrinterSettings";

export default function AdminPrinterPage() {
  const t = useTranslations("admin.printer");
  return (
    <>
      <Typography variant="h5" gutterBottom>
        {t("title")}
      </Typography>
      <AdminPrinterSettings />
    </>
  );
}
