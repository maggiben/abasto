"use client";

import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  LinearProgress,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditIcon from "@mui/icons-material/Edit";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import PrintIcon from "@mui/icons-material/Print";
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
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Dispatch, KeyboardEvent, SetStateAction } from "react";
import { Controller, useForm } from "react-hook-form";
import { apiFetch, ApiError, getApiBase } from "@/lib/api";
import { buildAdminProductListSearchParams } from "@/lib/adminProductListQuery";
import { authTokenAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import { isValidManualBarcode } from "@/lib/printProductLabel";
import { ProductLabelDialog } from "@/components/ProductLabelDialog";
import type {
  ProductBulkDeactivateResult,
  ProductCsvImportStart,
  ProductCsvImportStatus,
  ProductListPage,
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

type AdminProductsToolbarState = {
  q: string;
  includeInactive: boolean;
  stockHealth: "all" | "low" | "excess";
};

type AdminProductsToolbarContextValue = {
  gridToolbar: AdminProductsToolbarState;
  setGridToolbar: Dispatch<SetStateAction<AdminProductsToolbarState>>;
  setPaginationModel: Dispatch<SetStateAction<GridPaginationModel>>;
};

const AdminProductsToolbarContext = createContext<AdminProductsToolbarContextValue | null>(null);

/** Module-level so `slots.toolbar` identity is stable; inner components remount every parent render and break barcode scanners. */
function AdminProductsDataGridToolbar() {
  const ctx = useContext(AdminProductsToolbarContext);
  const t = useTranslations("admin");

  const searchInputProps = useMemo(
    () => ({
      spellCheck: false as const,
      autoComplete: "off" as const,
      "aria-label": "search",
      onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => {
        e.stopPropagation();
      },
    }),
    [],
  );

  if (!ctx) return null;
  const { gridToolbar, setGridToolbar, setPaginationModel } = ctx;

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
        inputProps={searchInputProps}
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
        <InputLabel id="admin-products-stock-health">{t("stockHealthFilter")}</InputLabel>
        <Select
          labelId="admin-products-stock-health"
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

export function AdminProducts() {
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
  const [rowMenu, setRowMenu] = useState<{ anchor: HTMLElement; row: ProductWithInventory } | null>(
    null,
  );
  const [labelDialog, setLabelDialog] = useState<{ name: string; barcode: string } | null>(null);
  const [labelPrinting, setLabelPrinting] = useState(false);
  const [labelErr, setLabelErr] = useState<string | null>(null);
  const [removeAllDialogOpen, setRemoveAllDialogOpen] = useState(false);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const importLastProcessedRef = useRef(0);

  const { register, handleSubmit, reset, control, formState, watch } = useForm<FormValues>({
    defaultValues: emptyForm,
  });

  const barcodeField = watch("barcode");
  const nameField = watch("name");

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

  const adminProductsToolbarContextValue = useMemo(
    (): AdminProductsToolbarContextValue => ({
      gridToolbar,
      setGridToolbar,
      setPaginationModel,
    }),
    [gridToolbar, setGridToolbar, setPaginationModel],
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

  const columns: GridColDef<ProductWithInventory>[] = useMemo(
    () => [
      { field: "name", headerName: t("name"), flex: 1, minWidth: 160 },
      { field: "brand", headerName: t("brand"), width: 120 },
      {
        field: "categoryDisplay",
        headerName: t("category"),
        flex: 0.8,
        minWidth: 120,
        valueGetter: (_v, row) =>
          row.category_detail ?? row.subcategory ?? row.category ?? "—",
      },
      { field: "barcode", headerName: t("barcode"), width: 140 },
      {
        field: "price",
        headerName: t("price"),
        type: "number",
        width: 110,
        align: "right",
        headerAlign: "right",
        valueGetter: (_v, row) => Number(row.price),
        renderCell: (params) => formatMoney(params.row.price),
      },
      {
        field: "stock",
        headerName: t("stock"),
        type: "number",
        width: 110,
        align: "right",
        headerAlign: "right",
        valueGetter: (_v, row) => Number(row.inventory?.quantity ?? 0),
        renderCell: (params) =>
          params.row.inventory ? formatMoney(params.row.inventory.quantity) : "—",
      },
      {
        field: "is_active",
        headerName: t("active"),
        type: "boolean",
        width: 100,
        valueGetter: (_v, row) => row.is_active,
      },
      {
        field: "actions",
        headerName: t("actions"),
        width: 72,
        align: "right",
        headerAlign: "right",
        sortable: false,
        filterable: false,
        disableColumnMenu: true,
        renderCell: (params) => (
          <IconButton
            aria-label={t("actionsMenu")}
            size="small"
            onClick={(e) => setRowMenu({ anchor: e.currentTarget, row: params.row })}
          >
            <MoreVertIcon fontSize="small" />
          </IconButton>
        ),
      },
    ],
    [t],
  );

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

  function openLabelPreview(name: string, barcode: string) {
    setLabelErr(null);
    setLabelDialog({ name, barcode });
  }

  async function sendThermalPrint() {
    if (!token || !labelDialog) return;
    setLabelErr(null);
    setLabelPrinting(true);
    try {
      await apiFetch<void>("/admin/products/print-label", {
        method: "POST",
        token,
        body: JSON.stringify({
          name: labelDialog.name.trim(),
          barcode: labelDialog.barcode.trim(),
        }),
      });
      setMsg(t("printThermalOk"));
      setLabelDialog(null);
    } catch (e) {
      setLabelErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setLabelPrinting(false);
    }
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

  async function activate(p: ProductWithInventory) {
    if (!token) return;
    setErr(null);
    try {
      await apiFetch(`/admin/products/${p.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ is_active: true }),
      });
      setMsg(t("productActivated"));
      void load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    }
  }

  async function permanentlyDelete(p: ProductWithInventory) {
    if (!token) return;
    if (!window.confirm(t("deletePermanentConfirm", { name: p.name }))) return;
    setErr(null);
    try {
      await apiFetch<void>(`/admin/products/${p.id}/permanent`, { method: "DELETE", token });
      setMsg(t("productDeletedPermanent"));
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

  function openRemoveAllDialog() {
    if (!token || importing || exporting || bulkRemoving) return;
    setRemoveAllDialogOpen(true);
  }

  async function confirmRemoveAllProducts() {
    if (!token || bulkRemoving) return;
    setErr(null);
    setMsg(null);
    setBulkRemoving(true);
    try {
      const res = await apiFetch<ProductBulkDeactivateResult>("/admin/products", {
        method: "DELETE",
        token,
      });
      setRemoveAllDialogOpen(false);
      setMsg(t("removeAllResult", { count: String(res.deactivated) }));
      void load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("removeAllFailed"));
    } finally {
      setBulkRemoving(false);
    }
  }

  const gridLocaleText = locale.startsWith("es")
    ? esES.components?.MuiDataGrid?.defaultProps?.localeText
    : undefined;

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
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
          onClick={openRemoveAllDialog}
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

      <AdminProductsToolbarContext.Provider value={adminProductsToolbarContextValue}>
        <Box sx={{ width: "100%", height: 560 }}>
          <DataGrid
            rows={rows}
            columns={columns}
            getRowId={(r) => r.id}
            loading={loading}
            rowCount={rowCount}
            paginationMode="server"
            paginationModel={paginationModel}
            onPaginationModelChange={(m) => setPaginationModel(m)}
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
            slots={{ toolbar: AdminProductsDataGridToolbar }}
            localeText={gridLocaleText}
            sx={{
              border: 1,
              borderColor: "divider",
              borderRadius: 1,
              "& .MuiDataGrid-cell:focus-within": { outline: "none" },
            }}
          />
        </Box>
      </AdminProductsToolbarContext.Provider>

      <Menu
        anchorEl={rowMenu?.anchor ?? null}
        open={Boolean(rowMenu)}
        onClose={() => setRowMenu(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <MenuItem
          disabled={!rowMenu?.row.barcode}
          onClick={() => {
            const r = rowMenu?.row;
            setRowMenu(null);
            if (r?.barcode) openLabelPreview(r.name, r.barcode);
          }}
        >
          <ListItemIcon>
            <PrintIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t("printLabel")}</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            const r = rowMenu?.row;
            setRowMenu(null);
            if (r) openEdit(r);
          }}
        >
          <ListItemIcon>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t("edit")}</ListItemText>
        </MenuItem>
        {rowMenu?.row == null ? null : rowMenu.row.is_active ? (
          <MenuItem
            onClick={() => {
              const r = rowMenu.row;
              setRowMenu(null);
              void deactivate(r);
            }}
          >
            <ListItemIcon>
              <DeleteOutlineIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>{t("deactivate")}</ListItemText>
          </MenuItem>
        ) : (
          <>
            <MenuItem
              onClick={() => {
                const r = rowMenu.row;
                setRowMenu(null);
                void activate(r);
              }}
            >
              <ListItemIcon>
                <CheckCircleOutlineIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>{t("activate")}</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                const r = rowMenu.row;
                setRowMenu(null);
                void permanentlyDelete(r);
              }}
              sx={{ color: "error.main" }}
            >
              <ListItemIcon>
                <DeleteForeverIcon fontSize="small" sx={{ color: "error.main" }} />
              </ListItemIcon>
              <ListItemText>{t("deletePermanently")}</ListItemText>
            </MenuItem>
          </>
        )}
      </Menu>

      <ProductLabelDialog
        open={Boolean(labelDialog)}
        onClose={() => setLabelDialog(null)}
        productName={labelDialog?.name ?? ""}
        barcode={labelDialog?.barcode ?? ""}
        onPrintThermal={sendThermalPrint}
        printing={labelPrinting}
        error={labelErr}
        title={t("labelPreviewTitle")}
        cancelLabel={t("cancel")}
        printThermalLabel={t("printThermal")}
      />

      <Dialog
        open={removeAllDialogOpen}
        onClose={() => {
          if (!bulkRemoving) setRemoveAllDialogOpen(false);
        }}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{t("removeAllDialogTitle")}</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <AlertTitle>{t("removeAllDialogAlertTitle")}</AlertTitle>
            {t("removeAllDialogAlertBody")}
          </Alert>
          <DialogContentText>{t("removeAllDialogBody")}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRemoveAllDialogOpen(false)} disabled={bulkRemoving}>
            {t("cancel")}
          </Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => void confirmRemoveAllProducts()}
            disabled={bulkRemoving}
          >
            {bulkRemoving ? t("removingAll") : t("removeAllConfirm")}
          </Button>
        </DialogActions>
      </Dialog>

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
                  disabled={
                    !barcodeField?.trim() ||
                    !isValidManualBarcode(barcodeField ?? "")
                  }
                  onClick={() =>
                    openLabelPreview(nameField?.trim() || "—", barcodeField ?? "")
                  }
                >
                  {t("previewLabel")}
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
