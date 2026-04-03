"use client";

import { CircularProgress, Stack, Typography } from "@mui/material";
import { useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import type { AnalyticsSummary } from "@/lib/types";

export default function AdminHomePage() {
  const t = useTranslations("admin");
  const [token] = useAtom(authTokenAtom);
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const s = await apiFetch<AnalyticsSummary>("/admin/analytics/summary", { token });
        if (!cancelled) setData(s);
      } catch (e) {
        if (!cancelled) setErr(e instanceof ApiError ? e.message : "—");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (err) {
    return <Typography color="error">{err}</Typography>;
  }
  if (loading || !data) {
    return (
      <Stack alignItems="center" py={4}>
        <CircularProgress />
      </Stack>
    );
  }

  const { totals } = data;
  return (
    <Stack spacing={2}>
      <Typography variant="h5">{t("summary")}</Typography>
      <Typography>
        {t("revenuePos")}: {formatMoney(totals.revenue_pos)}
      </Typography>
      <Typography>
        {t("revenueWeb")}: {formatMoney(totals.revenue_web)}
      </Typography>
      <Typography>
        {t("inventoryValue")}: {formatMoney(totals.inventory_value)}
      </Typography>
      <Typography>
        {t("posSales")}: {totals.pos_sale_count}
      </Typography>
    </Stack>
  );
}
