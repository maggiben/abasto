"use client";

import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import {
  DataGrid,
  GridToolbarContainer,
  type GridColDef,
} from "@mui/x-data-grid";
import { esES } from "@mui/x-data-grid/locales";
import { useLocale, useTranslations } from "next-intl";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { authTokenAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import { useRouter } from "@/i18n/navigation";
import type { CreditClientDetail, CreditClientSummary } from "@/lib/types";

export function AdminCreditAccounts() {
  const t = useTranslations("admin.creditAccounts");
  const locale = useLocale();
  const router = useRouter();
  const [token] = useAtom(authTokenAtom);

  const [rows, setRows] = useState<CreditClientSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQ(q), 300);
    return () => window.clearTimeout(id);
  }, [q]);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setErr(null);
    try {
      const params = new URLSearchParams();
      if (debouncedQ.trim()) params.set("q", debouncedQ.trim());
      if (includeInactive) params.set("include_inactive", "true");
      const data = await apiFetch<CreditClientSummary[]>(
        `/admin/credit-accounts?${params.toString()}`,
        { token },
      );
      setRows(data);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setLoading(false);
    }
  }, [token, debouncedQ, includeInactive]);

  useEffect(() => {
    void load();
  }, [load]);

  const createClient = useCallback(async () => {
    if (!token) return;
    if (!newName.trim()) {
      setErr(t("nameRequired"));
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const created = await apiFetch<CreditClientDetail>("/admin/credit-accounts", {
        method: "POST",
        token,
        body: JSON.stringify({
          name: newName.trim(),
          phone: newPhone.trim() || null,
          notes: newNotes.trim() || null,
        }),
      });
      setCreateOpen(false);
      setNewName("");
      setNewPhone("");
      setNewNotes("");
      setMsg(t("clientCreated"));
      router.push(`/admin/cuentas-corrientes/${created.id}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "—");
    } finally {
      setSaving(false);
    }
  }, [token, newName, newPhone, newNotes, t, router]);

  const columns: GridColDef<CreditClientSummary>[] = [
    {
      field: "name",
      headerName: t("clientName"),
      flex: 1,
      minWidth: 180,
      renderCell: (params) => (
        <Stack direction="row" spacing={1} alignItems="center" sx={{ height: "100%" }}>
          <span>{params.row.name}</span>
          {!params.row.is_active && (
            <Chip size="small" label={t("inactiveBadge")} color="default" variant="outlined" />
          )}
        </Stack>
      ),
    },
    { field: "phone", headerName: t("phone"), width: 150 },
    {
      field: "unpaid_item_count",
      headerName: t("unpaidItems"),
      type: "number",
      width: 130,
      align: "right",
      headerAlign: "right",
    },
    {
      field: "total_debt",
      headerName: t("totalDebt"),
      width: 160,
      align: "right",
      headerAlign: "right",
      valueGetter: (_v, row) => Number(row.total_debt),
      renderCell: (params) => (
        <Typography
          variant="body2"
          sx={{
            width: "100%",
            textAlign: "right",
            fontWeight: 600,
            color: Number(params.row.total_debt) > 0 ? "error.main" : "text.secondary",
          }}
        >
          {formatMoney(params.row.total_debt)}
        </Typography>
      ),
    },
  ];

  const gridLocaleText = locale.startsWith("es")
    ? esES.components?.MuiDataGrid?.defaultProps?.localeText
    : undefined;

  function Toolbar() {
    return (
      <GridToolbarContainer sx={{ flexWrap: "wrap", gap: 1, py: 1, alignItems: "center" }}>
        <TextField
          label={t("search")}
          size="small"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          sx={{ minWidth: 240 }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={includeInactive}
              onChange={(_, checked) => setIncludeInactive(checked)}
            />
          }
          label={t("showInactive")}
        />
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" onClick={() => setCreateOpen(true)}>
          {t("newClient")}
        </Button>
      </GridToolbarContainer>
    );
  }

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        {t("hint")}
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

      <Box sx={{ width: "100%", height: 540 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          getRowId={(r) => r.id}
          loading={loading}
          onRowClick={(p) => router.push(`/admin/cuentas-corrientes/${p.id}`)}
          initialState={{
            pagination: { paginationModel: { page: 0, pageSize: 25 } },
            sorting: { sortModel: [{ field: "name", sort: "asc" }] },
          }}
          pageSizeOptions={[25, 50, 100]}
          disableRowSelectionOnClick
          slots={{ toolbar: Toolbar }}
          localeText={gridLocaleText}
          sx={{
            border: 1,
            borderColor: "divider",
            borderRadius: 1,
            "& .MuiDataGrid-row": { cursor: "pointer" },
          }}
        />
      </Box>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("createClientTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("clientName")}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
              required
              fullWidth
            />
            <TextField
              label={t("phone")}
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
              fullWidth
            />
            <TextField
              label={t("notes")}
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>{t("cancel")}</Button>
          <Button variant="contained" onClick={() => void createClient()} disabled={saving}>
            {t("save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
