"use client";

import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import type { ReceiptPrinterConfigResolved } from "@/lib/types";

export function AdminPrinterSettings() {
  const t = useTranslations("admin.printer");
  const [token] = useAtom(authTokenAtom);
  const [form, setForm] = useState<ReceiptPrinterConfigResolved | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setLoadErr(null);
    try {
      const data = await apiFetch<ReceiptPrinterConfigResolved>("/admin/receipt-printer/settings", {
        token,
      });
      setForm(data);
    } catch (e) {
      setLoadErr(e instanceof ApiError ? e.message : String(e));
      setForm(null);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const patch = <K extends keyof ReceiptPrinterConfigResolved>(key: K, value: ReceiptPrinterConfigResolved[K]) => {
    setForm((f) => (f ? { ...f, [key]: value } : f));
    setSaveOk(false);
  };

  const onLogoFile = (file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const r = reader.result;
      if (typeof r === "string") {
        patch("logo_base64", r);
      }
    };
    reader.readAsDataURL(file);
  };

  const save = async () => {
    if (!token || !form) return;
    setSaveErr(null);
    setSaveOk(false);
    setBusy(true);
    try {
      const updated = await apiFetch<ReceiptPrinterConfigResolved>("/admin/receipt-printer/settings", {
        method: "PUT",
        token,
        body: JSON.stringify(form),
      });
      setForm(updated);
      setSaveOk(true);
    } catch (e) {
      setSaveErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const testPrint = async () => {
    if (!token) return;
    setSaveErr(null);
    setBusy(true);
    try {
      await apiFetch<void>("/admin/receipt-printer/test-print", {
        method: "POST",
        token,
      });
      setSaveOk(true);
    } catch (e) {
      setSaveErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (loadErr) {
    return <Alert severity="error">{loadErr}</Alert>;
  }

  if (!form) {
    return <Typography color="text.secondary">{t("loading")}</Typography>;
  }

  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }}>
      <Typography variant="body2" color="text.secondary">
        {t("intro")}
      </Typography>
      {saveErr ? <Alert severity="error">{saveErr}</Alert> : null}
      {saveOk ? <Alert severity="success">{t("savedOrPrinted")}</Alert> : null}

      <TextField
        label={t("storeName")}
        value={form.store_name}
        onChange={(e) => patch("store_name", e.target.value)}
        fullWidth
        helperText={t("storeNameHint")}
      />
      <TextField
        label={t("header")}
        value={form.header_text}
        onChange={(e) => patch("header_text", e.target.value)}
        fullWidth
        multiline
        minRows={2}
      />
      <TextField
        label={t("greeting")}
        value={form.greeting_text}
        onChange={(e) => patch("greeting_text", e.target.value)}
        fullWidth
        helperText={t("greetingHint")}
      />
      <TextField
        label={t("footer")}
        value={form.footer_text}
        onChange={(e) => patch("footer_text", e.target.value)}
        fullWidth
        multiline
        minRows={2}
      />
      <TextField
        label={t("closing")}
        value={form.closing_text}
        onChange={(e) => patch("closing_text", e.target.value)}
        fullWidth
        helperText={t("closingHint")}
      />

      <TextField
        select
        label={t("receiptLanguage")}
        value={form.receipt_locale}
        onChange={(e) => patch("receipt_locale", e.target.value as "es" | "en")}
        fullWidth
      >
        <MenuItem value="es">{t("localeEs")}</MenuItem>
        <MenuItem value="en">{t("localeEn")}</MenuItem>
      </TextField>

      <TextField
        type="number"
        label={t("feedLines")}
        value={form.feed_lines_before_cut}
        onChange={(e) => patch("feed_lines_before_cut", Math.max(0, Math.min(30, Number(e.target.value) || 0)))}
        fullWidth
        inputProps={{ min: 0, max: 30 }}
        helperText={t("feedLinesHint")}
      />

      <FormControlLabel
        control={
          <Switch
            checked={form.show_subtotal}
            onChange={(_, c) => patch("show_subtotal", c)}
          />
        }
        label={t("showSubtotal")}
      />
      <FormControlLabel
        control={
          <Switch
            checked={form.show_tax_lines}
            onChange={(_, c) => patch("show_tax_lines", c)}
          />
        }
        label={t("showTaxLines")}
      />
      <FormControlLabel
        control={
          <Switch
            checked={form.include_cashier_on_receipt}
            onChange={(_, c) => patch("include_cashier_on_receipt", c)}
          />
        }
        label={t("includeCashier")}
      />

      <Box>
        <Typography variant="subtitle2" gutterBottom>
          {t("logo")}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          {t("logoHint")}
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Button variant="outlined" component="label" size="small" disabled={busy}>
            {t("logoUpload")}
            <input
              type="file"
              hidden
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => onLogoFile(e.target.files?.[0] ?? null)}
            />
          </Button>
          <Button
            variant="text"
            size="small"
            disabled={busy || !form.logo_base64}
            onClick={() => patch("logo_base64", null)}
          >
            {t("logoClear")}
          </Button>
        </Stack>
        {form.logo_base64 ? (
          <TextField
            type="number"
            label={t("logoMaxWidth")}
            value={form.logo_max_width}
            onChange={(e) => patch("logo_max_width", Math.max(80, Math.min(576, Number(e.target.value) || 384)))}
            size="small"
            sx={{ mt: 1, maxWidth: 220 }}
            inputProps={{ min: 80, max: 576 }}
          />
        ) : null}
      </Box>

      <Stack direction="row" spacing={1} flexWrap="wrap">
        <Button variant="contained" onClick={() => void save()} disabled={busy}>
          {t("save")}
        </Button>
        <Button variant="outlined" onClick={() => void testPrint()} disabled={busy}>
          {t("testPrint")}
        </Button>
        <Button variant="text" onClick={() => void load()} disabled={busy}>
          {t("reload")}
        </Button>
      </Stack>
    </Stack>
  );
}
