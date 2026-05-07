"use client";

import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditIcon from "@mui/icons-material/Edit";
import PrintIcon from "@mui/icons-material/Print";
import { useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useCallback, useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { apiFetch, ApiError, getApiBase } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import { isValidManualBarcode, printProductLabel } from "@/lib/printProductLabel";
import type {
  ProductBulkDeactivateResult,
  ProductCsvImportStart,
  ProductCsvImportStatus,
  ProductWithInventory,
} from "@/lib/types";

type FormValues = {
  name: string;
  brand: string;
  category: string;
  subcategory: string;
  category_detail: string;
  price: string;
  cost: string;
  barcode: string;
  is_fractional: boolean;
};

const emptyForm: FormValues = {
  name: "",
  brand: "",
  category: "",
  subcategory: "",
  category_detail: "",
  price: "",
  cost: "",
  barcode: "",
  is_fractional: false,
};

export function AdminProducts() {
  const t = useTranslations("admin");
  const [token] = useAtom(authTokenAtom);
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<ProductWithInventory[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importJobId, setImportJobId] = useState<string | null>(null);
  const [importStatus, setImportStatus] = useState<ProductCsvImportStatus | null>(null);
  const [exporting, setExporting] = useState(false);
  const [bulkRemoving, setBulkRemoving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ProductWithInventory | null>(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const importLastProcessedRef = useRef(0);

  const { register, handleSubmit, reset, control, formState, watch } = useForm<FormValues>({
    defaultValues: emptyForm,
  });

  const barcodeField = watch("barcode");
  const nameField = watch("name");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setErr(null);
    try {
      const qs = new URLSearchParams({ limit: "200" });
      if (q.trim()) qs.set("q", q.trim());
      const list = await apiFetch<ProductWithInventory[]>(
        `/admin/products?${qs.toString()}`,
        { token },
      );
      setRows(list);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setLoading(false);
    }
  }, [token, q]);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 300);
    return () => window.clearTimeout(id);
  }, [load]);

  useEffect(() => {
    if (!token || !importJobId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const status = await apiFetch<ProductCsvImportStatus>(`/admin/products/import/${importJobId}`, {
          token,
        });
        if (cancelled) return;
        setImportStatus(status);
        if (status.processed > importLastProcessedRef.current) {
          importLastProcessedRef.current = status.processed;
          void load();
        }
        if (status.status === "completed") {
          setImporting(false);
          setImportJobId(null);
          setImportStatus(null);
          setMsg(
            t("importResult", {
              created: String(status.created),
              updated: String(status.updated),
            }),
          );
          void load();
        } else if (status.status === "failed") {
          setImporting(false);
          setImportJobId(null);
          setImportStatus(null);
          setErr(status.errors.join("\n") || t("importFailed"));
        }
      } catch (e) {
        if (cancelled) return;
        setImporting(false);
        setImportJobId(null);
        setImportStatus(null);
        setErr(e instanceof ApiError ? e.message : t("importFailed"));
      }
    };
    void poll();
    const timerId = window.setInterval(() => void poll(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timerId);
    };
  }, [token, importJobId, load, t]);

  function openCreate() {
    setEditing(null);
    reset(emptyForm);
    setOpen(true);
  }

  function openEdit(p: ProductWithInventory) {
    setEditing(p);
    reset({
      name: p.name,
      brand: p.brand ?? "",
      category: p.category ?? "",
      subcategory: p.subcategory ?? "",
      category_detail: p.category_detail ?? "",
      price: String(p.price),
      cost: p.cost ? String(p.cost) : "",
      barcode: p.barcode ?? "",
      is_fractional: p.is_fractional,
    });
    setOpen(true);
  }

  const onSave = handleSubmit(async (values) => {
    if (!token) return;
    setErr(null);
    try {
      const body = {
        name: values.name.trim(),
        brand: values.brand.trim() || null,
        category: values.category.trim() || null,
        subcategory: values.subcategory.trim() || null,
        category_detail: values.category_detail.trim() || null,
        price: values.price,
        cost: values.cost.trim() || null,
        barcode: values.barcode.trim() || null,
        is_fractional: values.is_fractional,
      };
      if (editing) {
        await apiFetch(`/admin/products/${editing.id}`, {
          method: "PATCH",
          token,
          body: JSON.stringify(body),
        });
      } else {
        await apiFetch(`/admin/products`, {
          method: "POST",
          token,
          body: JSON.stringify(body),
        });
      }
      setOpen(false);
      setMsg(t("save"));
      void load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    }
  });

  async function deactivate(p: ProductWithInventory) {
    if (!token) return;
    if (!window.confirm(p.name)) return;
    try {
      await apiFetch(`/admin/products/${p.id}`, { method: "DELETE", token });
      void load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    }
  }

  async function exportCsv() {
    if (!token || exporting || importing) return;
    setErr(null);
    setMsg(null);
    setExporting(true);
    try {
      const res = await fetch(`${getApiBase()}/admin/products/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setErr(t("exportFailed"));
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "products.csv";
      a.click();
      URL.revokeObjectURL(url);
      setMsg(t("exportSuccess"));
    } catch {
      setErr(t("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  async function importCsv(file: File | null) {
    if (!token || !file || importing || exporting) return;
    setErr(null);
    setMsg(null);
    setImportStatus(null);
    setImporting(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const start = await apiFetch<ProductCsvImportStart>("/admin/products/import", {
        method: "POST",
        token,
        body: fd,
      });
      importLastProcessedRef.current = 0;
      setImportJobId(start.job_id);
      setImportStatus({
        job_id: start.job_id,
        status: "queued",
        row_count: start.row_count,
        processed: 0,
        created: 0,
        updated: 0,
        errors: [],
      });
      setMsg(t("importStarted", { rows: String(start.row_count) }));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("importFailed"));
      setImporting(false);
    } finally {
      if (importInputRef.current) {
        importInputRef.current.value = "";
      }
    }
  }

  async function removeAllProducts() {
    if (!token || importing || exporting || bulkRemoving) return;
    const confirmed = window.confirm(t("removeAllWarning"));
    if (!confirmed) return;
    setErr(null);
    setMsg(null);
    setBulkRemoving(true);
    try {
      const res = await apiFetch<ProductBulkDeactivateResult>("/admin/products", {
        method: "DELETE",
        token,
      });
      setMsg(t("removeAllResult", { count: String(res.deactivated) }));
      void load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("removeAllFailed"));
    } finally {
      setBulkRemoving(false);
    }
  }

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
        <TextField
          label={t("search")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          size="small"
          sx={{ minWidth: 240 }}
        />
        <Button variant="contained" onClick={openCreate}>
          {t("newProduct")}
        </Button>
        <Button
          variant="outlined"
          onClick={() => void exportCsv()}
          disabled={importing || exporting || bulkRemoving}
        >
          {exporting ? t("exporting") : t("export")}
        </Button>
        <Button
          variant="outlined"
          component="label"
          disabled={importing || exporting || bulkRemoving}
        >
          {importing ? t("importing") : t("import")}
          <input
            ref={importInputRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(e) => void importCsv(e.target.files?.[0] ?? null)}
          />
        </Button>
        <Button
          variant="contained"
          color="error"
          onClick={() => void removeAllProducts()}
          disabled={importing || exporting || bulkRemoving}
        >
          {bulkRemoving ? t("removingAll") : t("removeAll")}
        </Button>
      </Stack>

      {err && (
        <Alert severity="error" onClose={() => setErr(null)}>
          {err}
        </Alert>
      )}
      {msg && (
        <Alert severity="success" onClose={() => setMsg(null)}>
          {msg}
        </Alert>
      )}
      {importStatus && (
        <Stack spacing={1}>
          <Typography variant="body2" color="text.secondary">
            {t("importProgress", {
              processed: String(importStatus.processed),
              total: String(importStatus.row_count),
              created: String(importStatus.created),
              updated: String(importStatus.updated),
            })}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={
              importStatus.row_count > 0
                ? Math.min((importStatus.processed / importStatus.row_count) * 100, 100)
                : 0
            }
          />
        </Stack>
      )}

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>{t("name")}</TableCell>
            <TableCell>{t("brand")}</TableCell>
            <TableCell>{t("category")}</TableCell>
            <TableCell>{t("barcode")}</TableCell>
            <TableCell align="right">{t("price")}</TableCell>
            <TableCell align="right">{t("stock")}</TableCell>
            <TableCell align="center">{t("active")}</TableCell>
            <TableCell align="right">{t("actions")}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {loading && (
            <TableRow>
              <TableCell colSpan={8}>
                <Typography color="text.secondary">…</Typography>
              </TableCell>
            </TableRow>
          )}
          {!loading &&
            rows.map((p) => (
              <TableRow key={p.id} hover>
                <TableCell>{p.name}</TableCell>
                <TableCell>{p.brand ?? "—"}</TableCell>
                <TableCell>{p.category_detail ?? p.subcategory ?? p.category ?? "—"}</TableCell>
                <TableCell>{p.barcode ?? "—"}</TableCell>
                <TableCell align="right">{formatMoney(p.price)}</TableCell>
                <TableCell align="right">
                  {p.inventory ? formatMoney(p.inventory.quantity) : "—"}
                </TableCell>
                <TableCell align="center">{p.is_active ? "✓" : "—"}</TableCell>
                <TableCell align="right">
                  {p.barcode ? (
                    <IconButton
                      aria-label={t("printLabel")}
                      size="small"
                      onClick={() => {
                        const ok = printProductLabel(p.name, p.barcode!);
                        if (!ok) setErr(t("printPopupBlocked"));
                      }}
                    >
                      <PrintIcon fontSize="small" />
                    </IconButton>
                  ) : null}
                  <IconButton
                    aria-label={t("edit")}
                    size="small"
                    onClick={() => openEdit(p)}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    aria-label={t("deactivate")}
                    size="small"
                    onClick={() => void deactivate(p)}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? t("edit") : t("newProduct")}</DialogTitle>
        <Box component="form" onSubmit={onSave}>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField label={t("name")} required {...register("name", { required: true })} />
              <TextField label={t("brand")} {...register("brand")} />
              <TextField label={t("category")} {...register("category")} />
              <TextField label={t("subcategory")} {...register("subcategory")} />
              <TextField label={t("categoryDetail")} {...register("category_detail")} />
              <TextField label={t("price")} required {...register("price", { required: true })} />
              <TextField label={t("cost")} {...register("cost")} />
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ xs: "stretch", sm: "flex-start" }}>
                <TextField
                  label={t("barcode")}
                  fullWidth
                  helperText={t("barcodeHint")}
                  {...register("barcode", {
                    validate: (v) =>
                      isValidManualBarcode(v) ? true : t("barcodeInvalid"),
                  })}
                />
                <Button
                  type="button"
                  variant="outlined"
                  sx={{ flexShrink: 0, mt: { xs: 0, sm: 1 } }}
                  startIcon={<PrintIcon />}
                  disabled={!barcodeField?.trim()}
                  onClick={() => {
                    const ok = printProductLabel(
                      nameField?.trim() || "—",
                      barcodeField ?? "",
                    );
                    if (!ok) setErr(t("printPopupBlocked"));
                  }}
                >
                  {t("printLabel")}
                </Button>
              </Stack>
              <Controller
                name="is_fractional"
                control={control}
                render={({ field }) => (
                  <FormControlLabel
                    control={
                      <Checkbox checked={field.value} onChange={(_, v) => field.onChange(v)} />
                    }
                    label="Fractional / weight"
                  />
                )}
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOpen(false)}>{t("cancel")}</Button>
            <Button type="submit" variant="contained" disabled={formState.isSubmitting}>
              {t("save")}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Stack>
  );
}
