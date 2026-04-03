"use client";

import {
  Alert,
  Button,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import type { InventoryPublic, ProductWithInventory } from "@/lib/types";

type RowDraft = { quantity: string; lowStockThreshold: string };

function draftFromProduct(p: ProductWithInventory): RowDraft {
  return {
    quantity: p.inventory?.quantity ?? "0",
    lowStockThreshold: p.inventory?.low_stock_threshold ?? "",
  };
}

export function AdminInventory() {
  const t = useTranslations("admin");
  const [token] = useAtom(authTokenAtom);
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<ProductWithInventory[]>([]);
  const [drafts, setDrafts] = useState<Record<number, RowDraft>>({});
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);

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
      const next: Record<number, RowDraft> = {};
      for (const p of list) next[p.id] = draftFromProduct(p);
      setDrafts(next);
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

  async function saveRow(productId: number) {
    if (!token) return;
    const d = drafts[productId];
    if (!d) return;
    const qtyTrim = d.quantity.trim();
    if (qtyTrim === "") {
      setErr(t("inventoryQtyRequired"));
      return;
    }
    const lowParsed =
      d.lowStockThreshold.trim() === "" ? null : d.lowStockThreshold.trim();
    setSavingId(productId);
    setErr(null);
    try {
      const inv = await apiFetch<InventoryPublic>(`/admin/inventory/products/${productId}`, {
        method: "PUT",
        token,
        body: JSON.stringify({
          quantity: qtyTrim,
          low_stock_threshold: lowParsed,
        }),
      });
      setRows((prev) =>
        prev.map((p) =>
          p.id === productId ? { ...p, inventory: inv } : p,
        ),
      );
      setDrafts((prev) => ({
        ...prev,
        [productId]: {
          quantity: inv.quantity,
          lowStockThreshold: inv.low_stock_threshold ?? "",
        },
      }));
      setMsg(t("inventorySaved"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        {t("inventoryHint")}
      </Typography>
      <TextField
        label={t("search")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        size="small"
        sx={{ minWidth: 240, maxWidth: 400 }}
      />

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
            <TableCell align="right">{t("inventoryQuantity")}</TableCell>
            <TableCell align="right">{t("lowStockThreshold")}</TableCell>
            <TableCell align="right">{t("actions")}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {loading && (
            <TableRow>
              <TableCell colSpan={5}>
                <Typography color="text.secondary">…</Typography>
              </TableCell>
            </TableRow>
          )}
          {!loading &&
            rows.map((p) => {
              const d = drafts[p.id] ?? draftFromProduct(p);
              return (
                <TableRow key={p.id} hover>
                  <TableCell>{p.name}</TableCell>
                  <TableCell>{p.barcode ?? "—"}</TableCell>
                  <TableCell align="right" sx={{ verticalAlign: "middle" }}>
                    <TextField
                      value={d.quantity}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [p.id]: { ...d, quantity: e.target.value },
                        }))
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          void saveRow(p.id);
                        }
                      }}
                      size="small"
                      type="text"
                      inputProps={{
                        inputMode: "decimal",
                        "aria-label": t("inventoryQuantity"),
                      }}
                      sx={{ width: 120 }}
                    />
                  </TableCell>
                  <TableCell align="right" sx={{ verticalAlign: "middle" }}>
                    <TextField
                      value={d.lowStockThreshold}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [p.id]: { ...d, lowStockThreshold: e.target.value },
                        }))
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          void saveRow(p.id);
                        }
                      }}
                      size="small"
                      type="text"
                      placeholder="—"
                      inputProps={{
                        inputMode: "decimal",
                        "aria-label": t("lowStockThreshold"),
                      }}
                      sx={{ width: 120 }}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      variant="outlined"
                      size="small"
                      disabled={savingId === p.id}
                      onClick={() => void saveRow(p.id)}
                    >
                      {t("save")}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
        </TableBody>
      </Table>
    </Stack>
  );
}
