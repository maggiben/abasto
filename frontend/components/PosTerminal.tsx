"use client";

import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  Snackbar,
  Stack,
  TextField,
  ThemeProvider,
  Typography,
  createTheme,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useAtom, useSetAtom } from "jotai";
import { apiFetch, ApiError } from "@/lib/api";
import { translatePosApiDetail } from "@/lib/posApiErrors";
import { PosAdminSwitchButton } from "@/components/PosAdminSwitchButton";
import { authTokenAtom, authUserAtom, clearAuthAtom } from "@/lib/atoms";
import { formatMoney } from "@/lib/format";
import type {
  CheckoutResponse,
  PosChargeAccountResponse,
  PosCreditClient,
  PriceCheckResponse,
  ProductCatalogItem,
} from "@/lib/types";

const posTheme = createTheme({
  palette: {
    mode: "dark",
    background: { default: "#0d1117", paper: "#161b22" },
    primary: { main: "#58a6ff" },
    success: { main: "#3fb950" },
  },
  typography: {
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, monospace",
    fontSize: 18,
    h6: { fontSize: "1.5rem", fontWeight: 600 },
    body1: { fontSize: "1.15rem" },
  },
  components: {
    MuiTextField: {
      defaultProps: { variant: "outlined", margin: "dense" },
    },
  },
});

type CartLine = {
  key: string;
  productId: number;
  name: string;
  quantity: string;
  unitPrice: string;
  taxRatePercent: string;
  isFractional: boolean;
};

function parseNum(s: string): number {
  const n = Number(String(s).replace(",", "."));
  return Number.isFinite(n) ? n : 0;
}

function stepFor(line: CartLine): number {
  return line.isFractional ? 0.05 : 1;
}

/** Must stay within `GET /catalog/products` `limit` max (see backend catalog route). */
const POS_CATALOG_SEARCH_LIMIT = 100;

export function PosTerminal() {
  const t = useTranslations("pos");
  const formatApiErr = useCallback(
    (message: string) => translatePosApiDetail(message, t),
    [t],
  );
  const [token] = useAtom(authTokenAtom);
  const [user] = useAtom(authUserAtom);
  const clearAuth = useSetAtom(clearAuthAtom);

  const searchRef = useRef<HTMLInputElement>(null);
  const linesRef = useRef<CartLine[]>([]);
  const selRef = useRef(0);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductCatalogItem[]>([]);
  const [pick, setPick] = useState(0);
  const [lines, setLines] = useState<CartLine[]>([]);
  const [sel, setSel] = useState(0);
  const [dry, setDry] = useState(false);
  const [calcOpen, setCalcOpen] = useState(false);
  const [calcExpr, setCalcExpr] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const [clients, setClients] = useState<PosCreditClient[]>([]);
  const [selectedClient, setSelectedClient] = useState<PosCreditClient | null>(null);
  const [clientQuery, setClientQuery] = useState("");
  const [charging, setCharging] = useState(false);

  useLayoutEffect(() => {
    linesRef.current = lines;
    selRef.current = sel;
  }, [lines, sel]);

  const totals = useMemo(() => {
    const taxEnvRaw = (process.env.NEXT_PUBLIC_POS_TAX_PERCENT ?? "").trim();
    const useFlatEnv = taxEnvRaw !== "";
    const flatPct = useFlatEnv ? Number(String(taxEnvRaw).replace(",", ".")) : NaN;

    let sub = 0;
    let tax = 0;
    for (const ln of lines) {
      const lineAmt = parseNum(ln.quantity) * parseNum(ln.unitPrice);
      sub += lineAmt;
      if (!useFlatEnv) {
        tax += lineAmt * (parseNum(ln.taxRatePercent) / 100);
      }
    }
    if (useFlatEnv && Number.isFinite(flatPct) && flatPct >= 0) {
      tax = sub * (flatPct / 100);
    }
    return { subtotal: sub, tax, total: sub + tax };
  }, [lines]);

  const focusSearch = useCallback(() => {
    searchRef.current?.focus();
    searchRef.current?.select();
  }, []);

  const clearSearchField = useCallback(() => {
    setQuery("");
    setResults([]);
    setPick(0);
    searchRef.current?.focus();
  }, []);

  const addProduct = useCallback(
    (p: ProductCatalogItem, qty = "1") => {
      const up = String(p.price);
      setLines((prev) => {
        const i = prev.findIndex(
          (l) => l.productId === p.id && l.unitPrice === up,
        );
        if (i >= 0) {
          const next = [...prev];
          const q = parseNum(next[i].quantity) + parseNum(qty);
          next[i] = { ...next[i], quantity: String(q) };
          return next;
        }
        return [
          ...prev,
          {
            key: crypto.randomUUID(),
            productId: p.id,
            name: p.name,
            quantity: qty,
            unitPrice: up,
            taxRatePercent: String(p.tax_rate_percent ?? "0"),
            isFractional: p.is_fractional,
          },
        ];
      });
      setQuery("");
      setResults([]);
      setMsg(p.name);
      focusSearch();
    },
    [focusSearch],
  );

  const resolveSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    if (dry) {
      try {
        const pc = await apiFetch<PriceCheckResponse>(
          `/catalog/price-check?barcode=${encodeURIComponent(q)}`,
        );
        setMsg(
          `${t("priceCheck")}: ${pc.name} — ${formatMoney(pc.price)} (${pc.quantity} stock)`,
        );
        setQuery("");
        focusSearch();
      } catch (e) {
        setErr(e instanceof ApiError ? formatApiErr(e.message) : t("checkoutErr"));
      }
      return;
    }
    try {
      const rows = await apiFetch<ProductCatalogItem[]>(
        `/catalog/products?q=${encodeURIComponent(q)}&limit=${POS_CATALOG_SEARCH_LIMIT}`,
      );
      if (rows.length === 0) {
        setErr(t("productNotInDatabase"));
        return;
      }
      if (rows.length === 1) {
        addProduct(rows[0]);
        return;
      }
      setResults(rows);
      setPick(0);
    } catch (e) {
      setErr(e instanceof ApiError ? formatApiErr(e.message) : t("checkoutErr"));
    }
  }, [query, dry, t, addProduct, focusSearch, formatApiErr]);

  const checkout = useCallback(async () => {
    if (!token || linesRef.current.length === 0) return;
    try {
      const taxEnvRaw = (process.env.NEXT_PUBLIC_POS_TAX_PERCENT ?? "").trim();
      const payload: Record<string, unknown> = {
        lines: linesRef.current.map((l) => ({
          product_id: l.productId,
          quantity: String(parseNum(l.quantity)),
          unit_price: l.unitPrice,
        })),
      };
      if (taxEnvRaw !== "") {
        const p = Number(String(taxEnvRaw).replace(",", "."));
        if (Number.isFinite(p) && p >= 0) {
          payload.tax_rate_percent = String(p);
        }
      }
      const res = await apiFetch<CheckoutResponse>("/pos/checkout", {
        method: "POST",
        token,
        body: JSON.stringify(payload as object),
      });
      setLines([]);
      setSel(0);
      setMsg(t("checkoutOk", { id: String(res.sale_id) }));
      focusSearch();
    } catch (e) {
      setErr(e instanceof ApiError ? formatApiErr(e.message) : t("checkoutErr"));
    }
  }, [token, t, focusSearch, formatApiErr]);

  const chargeAccount = useCallback(async () => {
    if (!token || linesRef.current.length === 0) return;
    if (!selectedClient) {
      setErr(t("selectClientFirst"));
      return;
    }
    setCharging(true);
    try {
      const res = await apiFetch<PosChargeAccountResponse>("/pos/credit-accounts/charge", {
        method: "POST",
        token,
        body: JSON.stringify({
          client_id: selectedClient.id,
          lines: linesRef.current.map((l) => ({
            product_id: l.productId,
            quantity: String(parseNum(l.quantity)),
          })),
        }),
      });
      setLines([]);
      setSel(0);
      setAccountOpen(false);
      setSelectedClient(null);
      setClientQuery("");
      setMsg(
        t("chargeAccountOk", {
          total: formatMoney(res.charged_total),
          name: res.client_name,
        }),
      );
      focusSearch();
    } catch (e) {
      setErr(e instanceof ApiError ? formatApiErr(e.message) : t("chargeAccountErr"));
    } finally {
      setCharging(false);
    }
  }, [token, selectedClient, t, focusSearch, formatApiErr]);

  // Load credit clients for the account picker (debounced search).
  useEffect(() => {
    if (!accountOpen || !token) return;
    const id = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams();
        if (clientQuery.trim()) params.set("q", clientQuery.trim());
        const rows = await apiFetch<PosCreditClient[]>(
          `/pos/credit-accounts?${params.toString()}`,
          { token },
        );
        setClients(rows);
      } catch {
        setClients([]);
      }
    }, 250);
    return () => window.clearTimeout(id);
  }, [accountOpen, token, clientQuery]);

  const removeLine = useCallback((index: number) => {
    setLines((prev) => {
      const next = prev.filter((_, i) => i !== index);
      setSel((s) => Math.min(s, Math.max(0, next.length - 1)));
      return next;
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const ae = document.activeElement as HTMLElement | null;
      const inSearch = ae === searchRef.current;
      const inEditable =
        ae &&
        (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA") &&
        ae !== searchRef.current;

      if (e.key === "F2") {
        e.preventDefault();
        setDry((d) => !d);
        return;
      }
      if (e.key === "F4") {
        e.preventDefault();
        void checkout();
        return;
      }
      if (e.key === "F6") {
        e.preventDefault();
        setCalcOpen((c) => !c);
        return;
      }
      if (e.key === "F7") {
        e.preventDefault();
        if (linesRef.current.length > 0) setAccountOpen(true);
        return;
      }
      if (e.key === "Escape") {
        setQuery("");
        setResults([]);
        setCalcOpen(false);
        return;
      }

      if (e.key === "ArrowDown" && results.length > 0 && inSearch) {
        e.preventDefault();
        setPick((p) => Math.min(p + 1, results.length - 1));
        return;
      }
      if (e.key === "ArrowUp" && results.length > 0 && inSearch) {
        e.preventDefault();
        setPick((p) => Math.max(p - 1, 0));
        return;
      }

      if (e.key === "Enter" && inSearch) {
        if (results.length > 0) {
          e.preventDefault();
          addProduct(results[pick]);
          setResults([]);
          return;
        }
        e.preventDefault();
        void resolveSearch();
        return;
      }

      const L = linesRef.current;
      const si = selRef.current;
      if (L.length === 0) return;

      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && !inEditable && !inSearch) {
        e.preventDefault();
        setSel((s) => {
          const n =
            e.key === "ArrowDown" ? Math.min(s + 1, L.length - 1) : Math.max(s - 1, 0);
          selRef.current = n;
          return n;
        });
        return;
      }

      const cartKeys = !inEditable && !inSearch;
      const addKey = e.key === "+" || e.key === "NumpadAdd";
      const subKey = e.key === "-" || e.key === "NumpadSubtract";
      if (cartKeys && (addKey || subKey)) {
        e.preventDefault();
        const line = L[si];
        if (!line) return;
        const step = stepFor(line);
        const dir = addKey ? 1 : -1;
        setLines((prev) => {
          const next = [...prev];
          const cur = next[si];
          if (!cur) return prev;
          const q = Math.max(0, parseNum(cur.quantity) + dir * step);
          next[si] = { ...cur, quantity: String(q) };
          return next;
        });
        return;
      }
      if (cartKeys && e.key === "Delete") {
        e.preventDefault();
        removeLine(si);
        return;
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [results, pick, resolveSearch, addProduct, checkout, removeLine]);

  useEffect(() => {
    focusSearch();
  }, [focusSearch]);

  function updateLine(i: number, patch: Partial<CartLine>) {
    setLines((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], ...patch };
      return next;
    });
  }

  function evalCalc(): void {
    const x = calcExpr.replace(/×/g, "*").replace(/÷/g, "/");
    if (!/^[-0-9+*/.()\s]+$/.test(x)) {
      setErr("calc");
      return;
    }
    try {
      const v = Function(`"use strict"; return (${x})`)() as number;
      if (typeof v === "number" && Number.isFinite(v)) {
        setCalcExpr(String(v));
        const i = selRef.current;
        if (linesRef.current[i]) {
          updateLine(i, { quantity: String(v) });
        }
      }
    } catch {
      setErr("calc");
    }
  }

  return (
    <ThemeProvider theme={posTheme}>
      <Box
        sx={{
          minHeight: "100vh",
          bgcolor: "background.default",
          color: "text.primary",
          p: 2,
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h6">{t("search")}</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button
              size="small"
              variant={dry ? "contained" : "outlined"}
              color={dry ? "success" : "inherit"}
              onClick={() => setDry((d) => !d)}
            >
              {t("dry")} (F2)
            </Button>
            {user?.is_staff ? (
              <PosAdminSwitchButton target="admin" title={t("openAdmin")} sx={{ mr: -0.5 }} />
            ) : null}
            <Button
              size="small"
              color="inherit"
              onClick={() => {
                clearAuth();
              }}
            >
              {t("logout")}
            </Button>
          </Stack>
        </Stack>

        <TextField
          inputRef={searchRef}
          fullWidth
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setResults([]);
          }}
          placeholder={dry ? t("priceCheck") : t("search")}
          autoComplete="off"
          inputProps={{ "aria-label": "search", spellCheck: false }}
          InputProps={{
            endAdornment: query ? (
              <InputAdornment position="end">
                <IconButton
                  aria-label={t("clearSearch")}
                  edge="end"
                  size="small"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={clearSearchField}
                >
                  <CloseIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ) : null,
          }}
        />

        {results.length > 1 && (
          <Box
            sx={{
              maxHeight: 200,
              overflow: "auto",
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
            }}
          >
            {results.map((r, i) => (
              <Box
                key={r.id}
                onClick={() => addProduct(r)}
                sx={{
                  px: 1,
                  py: 0.5,
                  cursor: "pointer",
                  bgcolor: i === pick ? "action.selected" : "transparent",
                }}
              >
                {r.name} · {formatMoney(r.price)}
              </Box>
            ))}
          </Box>
        )}

        <Typography variant="body2" color="text.secondary">
          {t("help")}
        </Typography>

        <Box sx={{ flex: 1, overflow: "auto" }}>
          <Typography variant="h6" gutterBottom>
            {t("cart")}
          </Typography>
          {lines.length === 0 ? (
            <Typography color="text.secondary">{t("empty")}</Typography>
          ) : (
            <Stack spacing={1}>
              {lines.map((ln, i) => (
                <Stack
                  key={ln.key}
                  direction={{ xs: "column", sm: "row" }}
                  spacing={1}
                  alignItems={{ sm: "center" }}
                  sx={{
                    p: 1,
                    borderRadius: 1,
                    border: "1px solid",
                    borderColor: i === sel ? "primary.main" : "divider",
                  }}
                  onClick={() => setSel(i)}
                >
                  <Typography sx={{ flex: 1 }}>{ln.name}</Typography>
                  <TextField
                    label={t("qty")}
                    value={ln.quantity}
                    onChange={(e) => updateLine(i, { quantity: e.target.value })}
                    sx={{ width: 120 }}
                    inputProps={{ inputMode: "decimal" }}
                  />
                  <TextField
                    label={t("price")}
                    value={ln.unitPrice}
                    onChange={(e) => updateLine(i, { unitPrice: e.target.value })}
                    sx={{ width: 140 }}
                    inputProps={{ inputMode: "decimal" }}
                  />
                  <Typography sx={{ minWidth: 100 }}>
                    {formatMoney(parseNum(ln.quantity) * parseNum(ln.unitPrice))}
                  </Typography>
                  <IconButton
                    aria-label={t("remove")}
                    color="error"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeLine(i);
                    }}
                  >
                    <DeleteOutlineIcon />
                  </IconButton>
                </Stack>
              ))}
            </Stack>
          )}
        </Box>

        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Box>
            <Typography>
              {t("subtotal")}: {formatMoney(totals.subtotal)}
            </Typography>
            <Typography>
              {t("tax")}: {formatMoney(totals.tax)}
            </Typography>
            <Typography variant="h6">
              {t("total")}: {formatMoney(totals.total)}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              size="large"
              color="primary"
              disabled={lines.length === 0}
              onClick={() => setAccountOpen(true)}
            >
              {t("chargeAccount")} (F7)
            </Button>
            <Button
              variant="contained"
              size="large"
              color="success"
              onClick={() => void checkout()}
            >
              {t("pay")} (F4)
            </Button>
          </Stack>
        </Stack>

        {calcOpen && (
          <Box sx={{ borderTop: "1px solid", borderColor: "divider", pt: 2 }}>
            <Typography gutterBottom>{t("calc")}</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <TextField
                value={calcExpr}
                onChange={(e) => setCalcExpr(e.target.value)}
                placeholder="1+2*3"
                sx={{ flex: 1, minWidth: 200 }}
              />
              <Button onClick={evalCalc}>=</Button>
            </Stack>
          </Box>
        )}

        <Dialog
          open={accountOpen}
          onClose={() => setAccountOpen(false)}
          fullWidth
          maxWidth="sm"
        >
          <DialogTitle>{t("chargeAccountTitle")}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {t("chargeAccountHint")}
              </Typography>
              <Autocomplete<PosCreditClient>
                options={clients}
                value={selectedClient}
                onChange={(_e, v) => setSelectedClient(v)}
                inputValue={clientQuery}
                onInputChange={(_e, v) => setClientQuery(v)}
                getOptionLabel={(o) => o.name}
                isOptionEqualToValue={(a, b) => a.id === b.id}
                filterOptions={(x) => x}
                noOptionsText={t("noCreditClients")}
                renderOption={(props, option) => (
                  <li {...props} key={option.id}>
                    <Stack>
                      <span>{option.name}</span>
                      <Typography variant="caption" color="text.secondary">
                        {option.phone ? `${option.phone} · ` : ""}
                        {t("currentDebt")}: {formatMoney(option.total_debt)}
                      </Typography>
                    </Stack>
                  </li>
                )}
                renderInput={(params) => (
                  <TextField {...params} label={t("selectClient")} autoFocus />
                )}
              />
              <Typography variant="h6">
                {t("subtotal")}: {formatMoney(totals.subtotal)}
              </Typography>
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAccountOpen(false)}>{t("cancel")}</Button>
            <Button
              variant="contained"
              disabled={!selectedClient || charging || lines.length === 0}
              onClick={() => void chargeAccount()}
            >
              {t("chargeAccountConfirm")}
            </Button>
          </DialogActions>
        </Dialog>

        <Snackbar
          open={!!msg}
          autoHideDuration={2500}
          onClose={() => setMsg(null)}
          message={msg}
          anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        />
        <Snackbar
          open={!!err}
          autoHideDuration={4000}
          onClose={() => setErr(null)}
          anchorOrigin={{ vertical: "top", horizontal: "center" }}
        >
          <Alert
            severity="error"
            action={
              <IconButton size="small" color="inherit" onClick={() => setErr(null)}>
                <CloseIcon fontSize="small" />
              </IconButton>
            }
          >
            {err}
          </Alert>
        </Snackbar>
      </Box>
    </ThemeProvider>
  );
}
