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
import { useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { apiFetch, ApiError, getApiBase } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import type { ProductCsvImportResult, ProductWithInventory } from "@/lib/types";

type FormValues = {
  name: string;
  price: string;
  cost: string;
  barcode: string;
  is_fractional: boolean;
};

const emptyForm: FormValues = {
  name: "",
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
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ProductWithInventory | null>(null);

  const { register, handleSubmit, reset, control, formState } = useForm<FormValues>({
    defaultValues: emptyForm,
  });

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

  function openCreate() {
    setEditing(null);
    reset(emptyForm);
    setOpen(true);
  }

  function openEdit(p: ProductWithInventory) {
    setEditing(p);
    reset({
      name: p.name,
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
    if (!token) return;
    const res = await fetch(`${getApiBase()}/admin/products/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setErr("export");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "products.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function importCsv(file: File | null) {
    if (!token || !file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await apiFetch<ProductCsvImportResult>("/admin/products/import", {
        method: "POST",
        token,
        body: fd,
      });
      setMsg(
        t("importResult", {
          created: String(r.created),
          updated: String(r.updated),
        }),
      );
      void load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
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
        <Button variant="outlined" onClick={() => void exportCsv()}>
          {t("export")}
        </Button>
        <Button variant="outlined" component="label">
          {t("import")}
          <input
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(e) => void importCsv(e.target.files?.[0] ?? null)}
          />
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

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>{t("name")}</TableCell>
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
              <TableCell colSpan={6}>
                <Typography color="text.secondary">…</Typography>
              </TableCell>
            </TableRow>
          )}
          {!loading &&
            rows.map((p) => (
              <TableRow key={p.id} hover>
                <TableCell>{p.name}</TableCell>
                <TableCell>{p.barcode ?? "—"}</TableCell>
                <TableCell align="right">{formatMoney(p.price)}</TableCell>
                <TableCell align="right">
                  {p.inventory ? formatMoney(p.inventory.quantity) : "—"}
                </TableCell>
                <TableCell align="center">{p.is_active ? "✓" : "—"}</TableCell>
                <TableCell align="right">
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
              <TextField label={t("price")} required {...register("price", { required: true })} />
              <TextField label={t("cost")} {...register("cost")} />
              <TextField label={t("barcode")} {...register("barcode")} />
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
