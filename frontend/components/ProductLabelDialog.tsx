"use client";

import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from "@mui/material";
import JsBarcode from "jsbarcode";
import { useTranslations } from "next-intl";
import { useCallback, useLayoutEffect, useRef, useState } from "react";

export type ProductLabelDialogProps = {
  open: boolean;
  onClose: () => void;
  productName: string;
  barcode: string;
  onPrintThermal: () => void | Promise<void>;
  printing: boolean;
  error: string | null;
  title: string;
  cancelLabel: string;
  printThermalLabel: string;
};

export function ProductLabelDialog({
  open,
  onClose,
  productName,
  barcode,
  onPrintThermal,
  printing,
  error,
  title,
  cancelLabel,
  printThermalLabel,
}: ProductLabelDialogProps) {
  const t = useTranslations("admin");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [encodeErr, setEncodeErr] = useState<string | null>(null);

  const drawBarcode = useCallback(() => {
    const canvas = canvasRef.current;
    const code = barcode.trim();
    if (!canvas || !code) return;

    try {
      setEncodeErr(null);
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }

      JsBarcode(canvas, code, {
        format: "CODE128",
        width: 2,
        height: 80,
        displayValue: true,
        fontSize: 14,
        margin: 12,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setEncodeErr(msg || t("barcodePreviewError"));
    }
  }, [barcode, t]);

  useLayoutEffect(() => {
    if (!open || !barcode.trim()) {
      setEncodeErr(null);
      return;
    }

    let cancelled = false;
    const safeDraw = () => {
      if (!cancelled) drawBarcode();
    };

    let rafOuter = 0;
    let rafInner = 0;
    rafOuter = requestAnimationFrame(() => {
      rafInner = requestAnimationFrame(safeDraw);
    });

    const timerFallback = window.setTimeout(safeDraw, 400);

    const wrap = wrapRef.current;
    let ro: ResizeObserver | undefined;
    if (wrap && typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => safeDraw());
      ro.observe(wrap);
    }

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafOuter);
      cancelAnimationFrame(rafInner);
      window.clearTimeout(timerFallback);
      ro?.disconnect();
    };
  }, [open, barcode, drawBarcode]);

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (!printing) onClose();
      }}
      fullWidth
      maxWidth="xs"
      sx={{ zIndex: (theme) => theme.zIndex.modal + 10 }}
    >
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Typography variant="body1" sx={{ fontWeight: 600, wordBreak: "break-word" }}>
            {productName.trim() || "—"}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "monospace" }}>
            {barcode.trim() || "—"}
          </Typography>
          <Box
            ref={wrapRef}
            sx={{
              width: "100%",
              display: "flex",
              justifyContent: "center",
              py: 1,
              overflow: "auto",
              minHeight: 120,
              alignItems: "center",
            }}
          >
            <canvas
              ref={canvasRef}
              style={{ maxWidth: "100%", height: "auto", verticalAlign: "middle" }}
            />
          </Box>
          {encodeErr && (
            <Alert severity="warning">
              {t("barcodePreviewError")}: {encodeErr}
            </Alert>
          )}
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={printing}>
          {cancelLabel}
        </Button>
        <Button
          variant="contained"
          onClick={() => void onPrintThermal()}
          disabled={printing || !barcode.trim()}
        >
          {printing ? <CircularProgress color="inherit" size={22} /> : printThermalLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
