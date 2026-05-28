"use client";

import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import {
  DataGrid,
  type GridColDef,
} from "@mui/x-data-grid";
import { esES } from "@mui/x-data-grid/locales";
import { useLocale, useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import { Link } from "@/i18n/navigation";
import type {
  CreditClientDetail,
  CreditItemOut,
  ProductCatalogItem,
} from "@/lib/types";

export function AdminCreditAccountDetail({ clientId }: { clientId: number }) {
  const t = useTranslations("admin.creditAccounts");
  const locale = useLocale();
  const [token] = useAtom(authTokenAtom);

  const [client, setClient] = useState<CreditClientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Add-item state
  const [productOptions, setProductOptions] = useState<ProductCatalogItem[]>([]);
  const [productInput, setProductInput] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<ProductCatalogItem | null>(null);
  const [quantity, setQuantity] = useState("1");
  const [itemNote, setItemNote] = useState("");

  // Selection + payment state
  const [selection, setSelection] = useState<number[]>([]);
  const [payOpen, setPayOpen] = useState(false);
  const [payNote, setPayNote] = useState("");

  // Edit client state
  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editNotes, setEditNotes] = useState("");

  // Remove-item confirm
  const [removeItem, setRemoveItem] = useState<CreditItemOut | null>(null);

  const dateFmt = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }),
    [locale],
  );

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<CreditClientDetail>(`/admin/credit-accounts/${clientId}`, {
        token,
      });
      setClient(data);
      setSelection((prev) => prev.filter((id) => data.items.some((it) => it.id === id)));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("loadError"));
    } finally {
      setLoading(false);
    }
  }, [token, clientId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  // Debounced product search for the add-item autocomplete.
  useEffect(() => {
    if (!token) return;
    const term = productInput.trim();
    const id = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({ limit: "20" });
        if (term) params.set("q", term);
        const data = await apiFetch<ProductCatalogItem[]>(
          `/catalog/products?${params.toString()}`,
          { token },
        );
        setProductOptions(data);
      } catch {
        setProductOptions([]);
      }
    }, 250);
    return () => window.clearTimeout(id);
  }, [token, productInput]);

  const addItem = useCallback(async () => {
    if (!token || !client) return;
    if (!selectedProduct) {
      setErr(t("selectProduct"));
      return;
    }
    const qty = Number(quantity);
    if (!Number.isFinite(qty) || qty <= 0) {
      setErr(t("quantityInvalid"));
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const data = await apiFetch<CreditClientDetail>(
        `/admin/credit-accounts/${client.id}/items`,
        {
          method: "POST",
          token,
          body: JSON.stringify({
            product_id: selectedProduct.id,
            quantity: quantity.trim(),
            note: itemNote.trim() || null,
          }),
        },
      );
      setClient(data);
      setSelectedProduct(null);
      setProductInput("");
      setQuantity("1");
      setItemNote("");
      setMsg(t("itemAdded"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setBusy(false);
    }
  }, [token, client, selectedProduct, quantity, itemNote, t]);

  const doRemoveItem = useCallback(async () => {
    if (!token || !client || !removeItem) return;
    setBusy(true);
    setErr(null);
    try {
      const data = await apiFetch<CreditClientDetail>(
        `/admin/credit-accounts/${client.id}/items/${removeItem.id}`,
        { method: "DELETE", token },
      );
      setClient(data);
      setMsg(t("itemRemoved"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setBusy(false);
      setRemoveItem(null);
    }
  }, [token, client, removeItem, t]);

  const registerPayment = useCallback(async () => {
    if (!token || !client || selection.length === 0) return;
    setBusy(true);
    setErr(null);
    try {
      const data = await apiFetch<CreditClientDetail>(
        `/admin/credit-accounts/${client.id}/payments`,
        {
          method: "POST",
          token,
          body: JSON.stringify({
            item_ids: selection,
            note: payNote.trim() || null,
          }),
        },
      );
      setClient(data);
      setSelection([]);
      setPayNote("");
      setPayOpen(false);
      setMsg(t("paymentRegistered"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setBusy(false);
    }
  }, [token, client, selection, payNote, t]);

  const saveEdit = useCallback(async () => {
    if (!token || !client) return;
    if (!editName.trim()) {
      setErr(t("nameRequired"));
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const data = await apiFetch<CreditClientDetail>(`/admin/credit-accounts/${client.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          name: editName.trim(),
          phone: editPhone.trim() || null,
          notes: editNotes.trim() || null,
        }),
      });
      setClient(data);
      setEditOpen(false);
      setMsg(t("clientSaved"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setBusy(false);
    }
  }, [token, client, editName, editPhone, editNotes, t]);

  const toggleActive = useCallback(async () => {
    if (!token || !client) return;
    setBusy(true);
    setErr(null);
    try {
      let data: CreditClientDetail;
      if (client.is_active) {
        data = await apiFetch<CreditClientDetail>(`/admin/credit-accounts/${client.id}`, {
          method: "DELETE",
          token,
        });
        setMsg(t("clientDeactivated"));
      } else {
        data = await apiFetch<CreditClientDetail>(`/admin/credit-accounts/${client.id}`, {
          method: "PATCH",
          token,
          body: JSON.stringify({ is_active: true }),
        });
      }
      setClient(data);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setBusy(false);
    }
  }, [token, client, t]);

  const selectedTotal = useMemo(() => {
    if (!client) return 0;
    return client.items
      .filter((it) => selection.includes(it.id))
      .reduce((sum, it) => sum + Number(it.line_total), 0);
  }, [client, selection]);

  const columns: GridColDef<CreditItemOut>[] = useMemo(
    () => [
      { field: "product_name", headerName: t("product"), flex: 1, minWidth: 200 },
      {
        field: "quantity",
        headerName: t("quantity"),
        type: "number",
        width: 110,
        align: "right",
        headerAlign: "right",
        valueGetter: (_v, row) => Number(row.quantity),
      },
      {
        field: "unit_price",
        headerName: t("unitPrice"),
        width: 130,
        align: "right",
        headerAlign: "right",
        valueGetter: (_v, row) => Number(row.unit_price),
        valueFormatter: (value) => formatMoney(value as number),
      },
      {
        field: "line_total",
        headerName: t("lineTotal"),
        width: 140,
        align: "right",
        headerAlign: "right",
        valueGetter: (_v, row) => Number(row.line_total),
        valueFormatter: (value) => formatMoney(value as number),
      },
      {
        field: "created_at",
        headerName: t("added"),
        width: 170,
        valueFormatter: (value) => dateFmt.format(new Date(value as string)),
      },
      {
        field: "note",
        headerName: t("itemNote"),
        flex: 0.6,
        minWidth: 120,
      },
      {
        field: "actions",
        headerName: "",
        width: 60,
        sortable: false,
        filterable: false,
        disableColumnMenu: true,
        align: "center",
        renderCell: (params) => (
          <Tooltip title={t("removeItem")}>
            <IconButton
              size="small"
              color="error"
              onClick={(e) => {
                e.stopPropagation();
                setRemoveItem(params.row);
              }}
            >
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
      },
    ],
    [t, dateFmt],
  );

  const gridLocaleText = locale.startsWith("es")
    ? esES.components?.MuiDataGrid?.defaultProps?.localeText
    : undefined;

  if (loading && !client) {
    return (
      <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!client) {
    return (
      <Stack spacing={2}>
        <Button
          component={Link}
          href="/admin/cuentas-corrientes"
          startIcon={<ArrowBackIcon />}
          sx={{ alignSelf: "flex-start" }}
        >
          {t("back")}
        </Button>
        <Alert severity="error">{err ?? t("loadError")}</Alert>
      </Stack>
    );
  }

  return (
    <Stack spacing={2}>
      <Button
        component={Link}
        href="/admin/cuentas-corrientes"
        startIcon={<ArrowBackIcon />}
        sx={{ alignSelf: "flex-start" }}
      >
        {t("back")}
      </Button>

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

      {/* Header */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          justifyContent="space-between"
          alignItems={{ sm: "center" }}
        >
          <Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h5">{client.name}</Typography>
              {!client.is_active && (
                <Chip size="small" label={t("inactiveBadge")} variant="outlined" />
              )}
            </Stack>
            {client.phone && (
              <Typography variant="body2" color="text.secondary">
                {t("phone")}: {client.phone}
              </Typography>
            )}
            {client.notes && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {client.notes}
              </Typography>
            )}
          </Box>
          <Box sx={{ textAlign: { sm: "right" } }}>
            <Typography variant="overline" color="text.secondary">
              {t("totalDebt")}
            </Typography>
            <Typography
              variant="h4"
              sx={{ fontWeight: 700, color: Number(client.total_debt) > 0 ? "error.main" : "success.main" }}
            >
              {formatMoney(client.total_debt)}
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1, justifyContent: { sm: "flex-end" } }}>
              <Button
                size="small"
                onClick={() => {
                  setEditName(client.name);
                  setEditPhone(client.phone ?? "");
                  setEditNotes(client.notes ?? "");
                  setEditOpen(true);
                }}
              >
                {t("edit")}
              </Button>
              <Button size="small" color="warning" disabled={busy} onClick={() => void toggleActive()}>
                {client.is_active ? t("deactivate") : t("reactivate")}
              </Button>
            </Stack>
          </Box>
        </Stack>
      </Paper>

      {/* Add item */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          {t("addItemTitle")}
        </Typography>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "flex-start" }}>
          <Autocomplete<ProductCatalogItem>
            options={productOptions}
            value={selectedProduct}
            onChange={(_e, value) => setSelectedProduct(value)}
            inputValue={productInput}
            onInputChange={(_e, value) => setProductInput(value)}
            getOptionLabel={(o) => o.name}
            isOptionEqualToValue={(o, v) => o.id === v.id}
            filterOptions={(x) => x}
            renderOption={(props, option) => (
              <li {...props} key={option.id}>
                <Stack>
                  <span>{option.name}</span>
                  <Typography variant="caption" color="text.secondary">
                    {formatMoney(option.price)}
                    {option.barcode ? ` · ${option.barcode}` : ""}
                  </Typography>
                </Stack>
              </li>
            )}
            sx={{ flex: 1, minWidth: 260 }}
            renderInput={(params) => (
              <TextField {...params} label={t("searchProduct")} size="small" />
            )}
          />
          <TextField
            label={t("quantity")}
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            size="small"
            inputProps={{ inputMode: "decimal" }}
            sx={{ width: 120 }}
          />
          <TextField
            label={t("itemNote")}
            value={itemNote}
            onChange={(e) => setItemNote(e.target.value)}
            size="small"
            sx={{ flex: 0.6, minWidth: 160 }}
          />
          <Button
            variant="contained"
            onClick={() => void addItem()}
            disabled={busy}
            sx={{ minWidth: 110, height: 40 }}
          >
            {t("add")}
          </Button>
        </Stack>
      </Paper>

      {/* Unpaid items */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={1}
          sx={{ mb: 1 }}
        >
          <Typography variant="subtitle1">{t("unpaidItemsTitle")}</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            {selection.length > 0 && (
              <Typography variant="body2" color="text.secondary">
                {formatMoney(selectedTotal)}
              </Typography>
            )}
            <Button
              variant="contained"
              disabled={selection.length === 0 || busy}
              onClick={() => setPayOpen(true)}
            >
              {t("chargeSelected")}
            </Button>
            <Button
              variant="outlined"
              disabled={client.items.length === 0 || busy}
              onClick={() => {
                setSelection(client.items.map((it) => it.id));
                setPayOpen(true);
              }}
            >
              {t("chargeAll")}
            </Button>
          </Stack>
        </Stack>

        {client.items.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
            {t("noUnpaidItems")}
          </Typography>
        ) : (
          <Box sx={{ width: "100%" }}>
            <DataGrid
              rows={client.items}
              columns={columns}
              getRowId={(r) => r.id}
              checkboxSelection
              disableRowSelectionOnClick
              rowSelectionModel={selection}
              onRowSelectionModelChange={(model) =>
                setSelection((model as Array<string | number>).map((id) => Number(id)))
              }
              autoHeight
              hideFooterSelectedRowCount
              initialState={{
                pagination: { paginationModel: { page: 0, pageSize: 50 } },
              }}
              pageSizeOptions={[25, 50, 100]}
              localeText={gridLocaleText}
              sx={{ border: 0 }}
            />
          </Box>
        )}
      </Paper>

      {/* Payment history */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          {t("paymentHistory")}
        </Typography>
        {client.payments.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t("noPayments")}
          </Typography>
        ) : (
          <Stack spacing={1.5}>
            {client.payments.map((p) => (
              <Box key={p.id}>
                <Stack direction="row" justifyContent="space-between" alignItems="baseline">
                  <Typography variant="body2" color="text.secondary">
                    {t("paidOn")}: {dateFmt.format(new Date(p.created_at))}
                  </Typography>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "success.main" }}>
                    {formatMoney(p.amount)}
                  </Typography>
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  {p.items
                    .map((si) => `${si.product_name} ×${Number(si.quantity)}`)
                    .join(", ")}
                </Typography>
                {p.note && (
                  <Typography variant="caption" display="block" color="text.secondary">
                    {p.note}
                  </Typography>
                )}
                <Divider sx={{ mt: 1 }} />
              </Box>
            ))}
          </Stack>
        )}
      </Paper>

      {/* Payment confirm dialog */}
      <Dialog
        open={payOpen}
        onClose={() => setPayOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>{t("paymentTitle")}</DialogTitle>
        <DialogContent>
          {selection.length === 0 ? (
            <DialogContentText>{t("noSelection")}</DialogContentText>
          ) : (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <DialogContentText>
                {t("paymentSummary", {
                  count: selection.length,
                  amount: formatMoney(selectedTotal),
                })}
              </DialogContentText>
              <TextField
                label={t("paymentNote")}
                value={payNote}
                onChange={(e) => setPayNote(e.target.value)}
                fullWidth
                multiline
                minRows={2}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPayOpen(false)}>{t("cancel")}</Button>
          <Button
            variant="contained"
            disabled={selection.length === 0 || busy}
            onClick={() => void registerPayment()}
          >
            {t("registerPayment")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit client dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("editClientTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("clientName")}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              required
              fullWidth
            />
            <TextField
              label={t("phone")}
              value={editPhone}
              onChange={(e) => setEditPhone(e.target.value)}
              fullWidth
            />
            <TextField
              label={t("notes")}
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>{t("cancel")}</Button>
          <Button variant="contained" disabled={busy} onClick={() => void saveEdit()}>
            {t("save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Remove item confirm */}
      <Dialog open={removeItem !== null} onClose={() => setRemoveItem(null)} maxWidth="xs">
        <DialogTitle>{t("removeItem")}</DialogTitle>
        <DialogContent>
          <DialogContentText>{t("removeItemConfirm")}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRemoveItem(null)}>{t("cancel")}</Button>
          <Button color="error" disabled={busy} onClick={() => void doRemoveItem()}>
            {t("removeItem")}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
