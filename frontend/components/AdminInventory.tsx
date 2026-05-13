"use client";

import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import {
  DataGrid,
  GridToolbarColumnsButton,
  GridToolbarContainer,
  GridToolbarDensitySelector,
  GridToolbarFilterButton,
  type GridColDef,
  type GridFilterModel,
  type GridPaginationModel,
  type GridSortModel,
} from "@mui/x-data-grid";
import { esES } from "@mui/x-data-grid/locales";
import { useLocale, useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { buildAdminProductListSearchParams } from "@/lib/adminProductListQuery";
import { authTokenAtom } from "@/lib/atoms";
import type { InventoryPublic, ProductListPage, ProductWithInventory } from "@/lib/types";

type RowDraft = { quantity: string; lowStockThreshold: string };

function draftFromProduct(p: ProductWithInventory): RowDraft {
  return {
    quantity: p.inventory?.quantity ?? "0",
    lowStockThreshold: p.inventory?.low_stock_threshold ?? "",
  };
}

export function AdminInventory() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const [token] = useAtom(authTokenAtom);
  const [rows, setRows] = useState<ProductWithInventory[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [sortModel, setSortModel] = useState<GridSortModel>([{ field: "id", sort: "desc" }]);
  const [filterModel, setFilterModel] = useState<GridFilterModel>({ items: [] });
  const [debouncedFilterModel, setDebouncedFilterModel] = useState<GridFilterModel>({ items: [] });
  const [gridToolbar, setGridToolbar] = useState({
    q: "",
    includeInactive: false,
    stockHealth: "all" as "all" | "low" | "excess",
  });
  const [debouncedSearchQ, setDebouncedSearchQ] = useState("");
  const [drafts, setDrafts] = useState<Record<number, RowDraft>>({});
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedFilterModel(filterModel), 400);
    return () => window.clearTimeout(id);
  }, [filterModel]);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedSearchQ(gridToolbar.q), 400);
    return () => window.clearTimeout(id);
  }, [gridToolbar.q]);

  const listToolbar = useMemo(
    () => ({
      q: debouncedSearchQ,
      includeInactive: gridToolbar.includeInactive,
      stockHealth: gridToolbar.stockHealth,
    }),
    [debouncedSearchQ, gridToolbar.includeInactive, gridToolbar.stockHealth],
  );

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setErr(null);
    try {
      const qs = buildAdminProductListSearchParams(
        paginationModel,
        sortModel,
        debouncedFilterModel,
        listToolbar,
      );
      const page = await apiFetch<ProductListPage>(`/admin/products?${qs}`, { token });
      setRows(page.items);
      setRowCount(page.total);
      const next: Record<number, RowDraft> = {};
      for (const p of page.items) next[p.id] = draftFromProduct(p);
      setDrafts(next);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setLoading(false);
    }
  }, [token, paginationModel, sortModel, debouncedFilterModel, listToolbar]);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 120);
    return () => window.clearTimeout(id);
  }, [load]);

  const saveRow = useCallback(async (productId: number) => {
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
  }, [token, drafts, t]);

  const columns: GridColDef<ProductWithInventory>[] = useMemo(
    () => [
      { field: "name", headerName: t("name"), flex: 1, minWidth: 180 },
      { field: "barcode", headerName: t("barcode"), width: 140 },
      {
        field: "quantity",
        headerName: t("inventoryQuantity"),
        type: "number",
        width: 150,
        align: "right",
        headerAlign: "right",
        valueGetter: (_v, row) => Number(row.inventory?.quantity ?? 0),
        renderCell: (params) => {
          const d = drafts[params.row.id] ?? draftFromProduct(params.row);
          return (
            <TextField
              value={d.quantity}
              onChange={(e) =>
                setDrafts((prev) => ({
                  ...prev,
                  [params.row.id]: { ...d, quantity: e.target.value },
                }))
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void saveRow(params.row.id);
                }
              }}
              size="small"
              type="text"
              inputProps={{
                inputMode: "decimal",
                "aria-label": t("inventoryQuantity"),
              }}
              sx={{ width: 120, mt: 0.5 }}
            />
          );
        },
      },
      {
        field: "lowStock",
        headerName: t("lowStockThreshold"),
        type: "number",
        width: 150,
        align: "right",
        headerAlign: "right",
        valueGetter: (_v, row) =>
          row.inventory?.low_stock_threshold != null &&
          String(row.inventory.low_stock_threshold).trim() !== ""
            ? Number(row.inventory.low_stock_threshold)
            : null,
        renderCell: (params) => {
          const d = drafts[params.row.id] ?? draftFromProduct(params.row);
          return (
            <TextField
              value={d.lowStockThreshold}
              onChange={(e) =>
                setDrafts((prev) => ({
                  ...prev,
                  [params.row.id]: { ...d, lowStockThreshold: e.target.value },
                }))
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void saveRow(params.row.id);
                }
              }}
              size="small"
              type="text"
              placeholder="—"
              inputProps={{
                inputMode: "decimal",
                "aria-label": t("lowStockThreshold"),
              }}
              sx={{ width: 120, mt: 0.5 }}
            />
          );
        },
      },
      {
        field: "save",
        headerName: t("actions"),
        width: 100,
        sortable: false,
        filterable: false,
        disableColumnMenu: true,
        align: "right",
        headerAlign: "right",
        renderCell: (params) => (
          <Button
            variant="outlined"
            size="small"
            disabled={savingId === params.row.id}
            onClick={() => void saveRow(params.row.id)}
            sx={{ mt: 0.5 }}
          >
            {t("save")}
          </Button>
        ),
      },
    ],
    [t, drafts, savingId, saveRow],
  );

  function InventoryToolbar() {
    return (
      <GridToolbarContainer sx={{ flexWrap: "wrap", gap: 1, py: 1, alignItems: "center" }}>
        <GridToolbarColumnsButton />
        <GridToolbarFilterButton />
        <GridToolbarDensitySelector />
        <TextField
          label={t("search")}
          size="small"
          value={gridToolbar.q}
          onChange={(e) => {
            setGridToolbar((g) => ({ ...g, q: e.target.value }));
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          sx={{ minWidth: 200 }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={gridToolbar.includeInactive}
              onChange={(_, checked) => {
                setGridToolbar((g) => ({ ...g, includeInactive: checked }));
                setPaginationModel((p) => ({ ...p, page: 0 }));
              }}
            />
          }
          label={t("showInactive")}
        />
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="admin-inv-stock-health">{t("stockHealthFilter")}</InputLabel>
          <Select
            labelId="admin-inv-stock-health"
            label={t("stockHealthFilter")}
            value={gridToolbar.stockHealth}
            onChange={(e) => {
              setGridToolbar((g) => ({
                ...g,
                stockHealth: e.target.value as "all" | "low" | "excess",
              }));
              setPaginationModel((p) => ({ ...p, page: 0 }));
            }}
          >
            <MenuItem value="all">{t("stockHealthAll")}</MenuItem>
            <MenuItem value="low">{t("stockHealthLow")}</MenuItem>
            <MenuItem value="excess">{t("stockHealthExcess")}</MenuItem>
          </Select>
        </FormControl>
      </GridToolbarContainer>
    );
  }

  const gridLocaleText = locale.startsWith("es")
    ? esES.components?.MuiDataGrid?.defaultProps?.localeText
    : undefined;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        {t("inventoryHint")}
      </Typography>

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

      <Box sx={{ width: "100%", height: 520 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          getRowId={(r) => r.id}
          loading={loading}
          rowCount={rowCount}
          paginationMode="server"
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          pageSizeOptions={[25, 50, 100, 200]}
          sortingMode="server"
          sortModel={sortModel}
          onSortModelChange={(m) => {
            setSortModel(m);
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          filterMode="server"
          filterModel={filterModel}
          onFilterModelChange={(m) => {
            setFilterModel(m);
            setPaginationModel((p) => ({ ...p, page: 0 }));
          }}
          disableRowSelectionOnClick
          slots={{ toolbar: InventoryToolbar }}
          localeText={gridLocaleText}
          sx={{
            border: 1,
            borderColor: "divider",
            borderRadius: 1,
            "& .MuiDataGrid-cell:focus-within": { outline: "none" },
          }}
        />
      </Box>
    </Stack>
  );
}
