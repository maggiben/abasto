"use client";

import { Typography } from "@mui/material";
import { useTranslations } from "next-intl";
import { AdminProducts } from "@/components/AdminProducts";

export default function AdminProductsPage() {
  const t = useTranslations("admin");
  return (
    <>
      <Typography variant="h5" gutterBottom>
        {t("products")}
      </Typography>
      <AdminProducts />
    </>
  );
}
