"use client";

import { BarChart } from "@mui/x-charts/BarChart";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  FormControlLabel,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { useAtom } from "jotai";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import type {
  AnalyticsSummary,
  Granularity,
  PresetKey,
  ResetSalesOut,
  TopSellersOut,
} from "@/lib/types";

function computeWesternEasterLocal(year: number): Date {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month - 1, day);
}

function parseYmdLocal(ymd: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (!y || mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  const dt = new Date(y, mo - 1, d, 0, 0, 0, 0);
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null;
  return dt;
}

function addDaysLocal(d: Date, days: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + days);
  return x;
}

function rangeForPreset(
  key: PresetKey,
  customFrom: string,
  customTo: string,
  now: Date,
): { start: Date; endExclusive: Date } | null {
  if (key === "custom") {
    const a = parseYmdLocal(customFrom);
    const b = parseYmdLocal(customTo);
    if (!a || !b) return null;
    if (b < a) return null;
    return { start: a, endExclusive: addDaysLocal(b, 1) };
  }
  if (key === "7d") {
    return { start: addDaysLocal(now, -7), endExclusive: now };
  }
  if (key === "30d") {
    return { start: addDaysLocal(now, -30), endExclusive: now };
  }
  if (key === "90d") {
    return { start: addDaysLocal(now, -90), endExclusive: now };
  }
  if (key === "this_month") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    return { start, endExclusive: now };
  }
  if (key === "prev_month") {
    const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const endExclusive = new Date(now.getFullYear(), now.getMonth(), 1);
    return { start, endExclusive };
  }
  if (key === "ytd") {
    const start = new Date(now.getFullYear(), 0, 1);
    return { start, endExclusive: now };
  }
  if (key === "christmas") {
    let y = now.getFullYear();
    if (now < new Date(y, 11, 1)) {
      y -= 1;
    }
    const start = new Date(y, 11, 1);
    const endExclusive = new Date(y + 1, 0, 1);
    return { start, endExclusive };
  }
  if (key === "holy_week") {
    const y = now.getFullYear();
    const e = computeWesternEasterLocal(y);
    const start = addDaysLocal(e, -6);
    const endExclusive = addDaysLocal(e, 1);
    return { start, endExclusive };
  }
  return null;
}

function formatBucketLabel(iso: string, granularity: Granularity, locale: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (granularity === "day") {
    return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
  }
  if (granularity === "week") {
    return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
  }
  if (granularity === "month") {
    return d.toLocaleDateString(locale, { month: "short", year: "numeric" });
  }
  return d.toLocaleDateString(locale, { year: "numeric" });
}

function moneyNum(s: string): number {
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

export function AdminDashboard() {
  const t = useTranslations("admin.dashboard");
  const ta = useTranslations("admin");
  const [token] = useAtom(authTokenAtom);
  const [preset, setPreset] = useState<PresetKey>("30d");
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [tops, setTops] = useState<TopSellersOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const [resetDialogErr, setResetDialogErr] = useState<string | null>(null);
  const [resetBanner, setResetBanner] = useState<string | null>(null);
  const [restoreInventoryOnReset, setRestoreInventoryOnReset] = useState(false);

  const rangeNow = useMemo(
    () => rangeForPreset(preset, customFrom, customTo, new Date()),
    [preset, customFrom, customTo],
  );

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    const r = rangeForPreset(preset, customFrom, customTo, new Date());
    if (!r) {
      setLoading(false);
      setSummary(null);
      setTops(null);
      return;
    }
    const p = new URLSearchParams();
    p.set("range_start", r.start.toISOString());
    p.set("range_end", r.endExclusive.toISOString());
    p.set("granularity", granularity);
    const qs = p.toString();
    setLoading(true);
    setErr(null);
    try {
      const [s, top] = await Promise.all([
        apiFetch<AnalyticsSummary>(`/admin/analytics/summary?${qs}`, { token }),
        apiFetch<TopSellersOut>(`/admin/analytics/top-sellers?${qs}&limit=8`, { token }),
      ]);
      setSummary(s);
      setTops(top);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
      setSummary(null);
      setTops(null);
    } finally {
      setLoading(false);
    }
  }, [token, preset, customFrom, customTo, granularity]);

  useEffect(() => {
    void load();
  }, [load]);

  const locale =
    typeof navigator !== "undefined" && navigator.language ? navigator.language : "es";

  const revenueRows = useMemo(() => {
    if (!summary) return [];
    return summary.buckets.map((b) => ({
      label: formatBucketLabel(b.period_start, summary.granularity, locale),
      pos: moneyNum(b.revenue_pos),
      web: moneyNum(b.revenue_web),
      total: moneyNum(b.revenue_pos) + moneyNum(b.revenue_web),
    }));
  }, [summary, locale]);

  const productRows = useMemo(() => {
    if (!tops) return [];
    return tops.products.map((p) => ({
      name: p.name.length > 36 ? `${p.name.slice(0, 34)}…` : p.name,
      revenue: moneyNum(p.revenue),
      qty: Number(p.quantity_sold),
    }));
  }, [tops]);

  const categoryRows = useMemo(() => {
    if (!tops) return [];
    return tops.categories.map((c) => ({
      name: c.category === "—" ? t("uncategorized") : c.category,
      revenue: moneyNum(c.revenue),
      qty: Number(c.quantity_sold),
    }));
  }, [tops, t]);

  if (!token) {
    return null;
  }
  if (err) {
    return <Typography color="error">{err}</Typography>;
  }
  if (preset === "custom" && !rangeNow) {
    return (
      <Stack spacing={2}>
        <Typography variant="h5">{t("title")}</Typography>
        <Typography color="text.secondary">{t("customInvalid")}</Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="flex-start">
          <TextField
            label={t("from")}
            type="date"
            value={customFrom}
            onChange={(e) => setCustomFrom(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            label={t("to")}
            type="date"
            value={customTo}
            onChange={(e) => setCustomTo(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Stack>
      </Stack>
    );
  }
  if (loading || !summary || !tops) {
    return (
      <Stack alignItems="center" py={4}>
        <CircularProgress />
      </Stack>
    );
  }

  const { totals } = summary;
  const orders = totals.pos_sale_count + totals.web_order_count;
  const aov = orders > 0 ? moneyNum(totals.revenue_total) / orders : 0;

  return (
    <Stack spacing={3}>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        alignItems={{ xs: "stretch", md: "center" }}
        justifyContent="space-between"
      >
        <Typography variant="h5" component="h1">
          {t("title")}
        </Typography>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={granularity}
          onChange={(_, v: Granularity | null) => {
            if (v) setGranularity(v);
          }}
          aria-label={t("granularity")}
        >
          <ToggleButton value="day">{t("byDay")}</ToggleButton>
          <ToggleButton value="week">{t("byWeek")}</ToggleButton>
          <ToggleButton value="month">{t("byMonth")}</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          {t("range")}
        </Typography>
        <Stack direction="row" flexWrap="wrap" gap={1}>
          {(
            [
              ["7d", t("p7d")],
              ["30d", t("p30d")],
              ["90d", t("p90d")],
              ["this_month", t("thisMonth")],
              ["prev_month", t("prevMonth")],
              ["ytd", t("ytd")],
              ["custom", t("custom")],
            ] as const
          ).map(([k, label]) => (
            <Button
              key={k}
              variant={preset === k ? "contained" : "outlined"}
              size="small"
              onClick={() => setPreset(k)}
            >
              {label}
            </Button>
          ))}
        </Stack>
        {preset === "custom" ? (
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 2 }}>
            <TextField
              label={t("from")}
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              label={t("to")}
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
        ) : null}
      </Box>

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: {
            xs: "1fr",
            sm: "repeat(2, 1fr)",
            md: "repeat(auto-fill, minmax(200px, 1fr))",
          },
        }}
      >
        <Card variant="outlined">
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              {t("kpiTotal")}
            </Typography>
            <Typography variant="h6">{formatMoney(totals.revenue_total)}</Typography>
          </CardContent>
        </Card>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              {t("kpiPos")}
            </Typography>
            <Typography variant="h6">{formatMoney(totals.revenue_pos)}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t("tickets", { count: totals.pos_sale_count })}
            </Typography>
          </CardContent>
        </Card>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              {t("kpiWeb")}
            </Typography>
            <Typography variant="h6">{formatMoney(totals.revenue_web)}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t("orders", { count: totals.web_order_count })}
            </Typography>
          </CardContent>
        </Card>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              {t("kpiAov")}
            </Typography>
            <Typography variant="h6">{formatMoney(aov)}</Typography>
            <Typography variant="body2" color="text.secondary">
              {ta("inventoryValue")}: {formatMoney(totals.inventory_value)}
            </Typography>
          </CardContent>
        </Card>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              {t("kpiGrossProfit")}
            </Typography>
            <Typography variant="h6">{formatMoney(totals.gross_profit)}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t("kpiGrossProfitHint")}
            </Typography>
          </CardContent>
        </Card>
      </Box>

      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle1" gutterBottom>
            {t("chartRevenue")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {t("chartRevenueHint")}
          </Typography>
          {revenueRows.length === 0 ? (
            <Typography color="text.secondary">{t("noBuckets")}</Typography>
          ) : (
            <BarChart
              dataset={revenueRows}
              xAxis={[{ scaleType: "band", dataKey: "label" }]}
              series={[
                {
                  dataKey: "pos",
                  label: t("seriesPos"),
                  valueFormatter: (v) => formatMoney(v ?? 0),
                },
                {
                  dataKey: "web",
                  label: t("seriesWeb"),
                  valueFormatter: (v) => formatMoney(v ?? 0),
                },
              ]}
              height={320}
              margin={{ top: 16, right: 16, bottom: 56, left: 56 }}
              slotProps={{
                legend: {
                  direction: "row",
                  position: { vertical: "bottom", horizontal: "middle" },
                },
              }}
            />
          )}
        </CardContent>
      </Card>

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" },
        }}
      >
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>
              {t("topProducts")}
            </Typography>
            {productRows.length === 0 ? (
              <Typography color="text.secondary">{t("noRankings")}</Typography>
            ) : (
              <BarChart
                dataset={[...productRows].reverse()}
                layout="horizontal"
                yAxis={[{ scaleType: "band", dataKey: "name" }]}
                xAxis={[{ min: 0 }]}
                series={[
                  {
                    dataKey: "revenue",
                    label: t("revenue"),
                    valueFormatter: (v) => formatMoney(v ?? 0),
                  },
                ]}
                height={Math.max(220, productRows.length * 36)}
                margin={{ top: 8, right: 16, bottom: 48, left: 140 }}
                slotProps={{
                  legend: {
                    direction: "row",
                    position: { vertical: "bottom", horizontal: "middle" },
                  },
                }}
              />
            )}
          </CardContent>
        </Card>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>
              {t("topCategories")}
            </Typography>
            {categoryRows.length === 0 ? (
              <Typography color="text.secondary">{t("noRankings")}</Typography>
            ) : (
              <BarChart
                dataset={[...categoryRows].reverse()}
                layout="horizontal"
                yAxis={[{ scaleType: "band", dataKey: "name" }]}
                xAxis={[{ min: 0 }]}
                series={[
                  {
                    dataKey: "revenue",
                    label: t("revenue"),
                    valueFormatter: (v) => formatMoney(v ?? 0),
                  },
                ]}
                height={Math.max(220, categoryRows.length * 36)}
                margin={{ top: 8, right: 16, bottom: 48, left: 140 }}
                slotProps={{
                  legend: {
                    direction: "row",
                    position: { vertical: "bottom", horizontal: "middle" },
                  },
                }}
              />
            )}
          </CardContent>
        </Card>
      </Box>


      <Divider sx={{ my: 1 }} />

      <Box
        sx={{
          p: 2,
          borderRadius: 1,
          border: "1px solid",
          borderColor: "divider",
          bgcolor: "action.hover",
          maxWidth: 480,
        }}
      >
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          {t("resetSectionTitle")}
        </Typography>
        {resetBanner ? (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setResetBanner(null)}>
            {resetBanner}
          </Alert>
        ) : null}
        <Button
          variant="contained"
          color="error"
          onClick={() => {
            setResetDialogErr(null);
            setRestoreInventoryOnReset(false);
            setResetDialogOpen(true);
          }}
        >
          {t("resetSalesButton")}
        </Button>
      </Box>

      <Divider />
      <Typography variant="caption" color="text.secondary">
        {t("footerRange", {
          start: new Date(summary.range_start).toLocaleString(locale),
          end: new Date(summary.range_end).toLocaleString(locale),
        })}
      </Typography>

      <Dialog
        open={resetDialogOpen}
        onClose={() => {
          if (!resetBusy) setResetDialogOpen(false);
        }}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{t("resetSalesDialogTitle")}</DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mb: 2 }}>
            <AlertTitle>{t("resetSalesDialogAlertTitle")}</AlertTitle>
            {t("resetSalesDialogAlertBody")}
          </Alert>
          <DialogContentText sx={{ mb: 1 }}>{t("resetSalesDialogBody")}</DialogContentText>
          <FormControlLabel
            sx={{ alignItems: "flex-start", ml: 0, mr: 0 }}
            control={
              <Checkbox
                checked={restoreInventoryOnReset}
                onChange={(_, checked) => setRestoreInventoryOnReset(checked)}
                disabled={resetBusy}
              />
            }
            label={
              <Box>
                <Typography variant="body2">{t("resetSalesRestoreInventory")}</Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  {t("resetSalesRestoreInventoryHint")}
                </Typography>
              </Box>
            }
          />
          {resetDialogErr ? (
            <Alert severity="error" sx={{ mt: 2 }}>
              {resetDialogErr}
            </Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetDialogOpen(false)} disabled={resetBusy}>
            {t("resetSalesCancel")}
          </Button>
          <Button
            variant="contained"
            color="error"
            disabled={resetBusy}
            onClick={async () => {
              if (!token) return;
              setResetBusy(true);
              setResetDialogErr(null);
              try {
                const out = await apiFetch<ResetSalesOut>("/admin/sales/reset-all", {
                  method: "POST",
                  token,
                  body: JSON.stringify({ restore_inventory: restoreInventoryOnReset }),
                });
                setResetDialogOpen(false);
                setRestoreInventoryOnReset(false);
                setResetBanner(
                  `${t("resetSalesSuccess", {
                    pos: out.pos_tickets_removed,
                    web: out.web_orders_removed,
                  })} ${out.inventory_restored ? t("resetSalesSuccessInventoryOn") : t("resetSalesSuccessInventoryOff")}`,
                );
                await load();
              } catch (e) {
                if (e instanceof ApiError && e.status === 403) {
                  setResetDialogErr(t("resetSalesDisabled"));
                } else {
                  setResetDialogErr(e instanceof ApiError ? e.message : "—");
                }
              } finally {
                setResetBusy(false);
              }
            }}
          >
            {resetBusy ? t("resetSalesRunning") : t("resetSalesConfirm")}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
