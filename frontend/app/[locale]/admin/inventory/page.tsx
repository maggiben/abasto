"use client";

import { Typography } from "@mui/material";
import { useTranslations } from "next-intl";
import { AdminInventory } from "@/components/AdminInventory";

export default function AdminInventoryPage() {
  const t = useTranslations("admin");
  return (
    <>
      <Typography variant="h5" gutterBottom>
        {t("inventoryTitle")}
      </Typography>
      <AdminInventory />
    </>
  );
}
