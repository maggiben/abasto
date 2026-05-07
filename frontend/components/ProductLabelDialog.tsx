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
import { useEffect, useRef } from "react";

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
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const el = svgRef.current;
    if (!open || !el) return;
    const code = barcode.trim();
    if (!code) return;
    try {
      el.replaceChildren();
      JsBarcode(el, code, {
        format: "CODE128",
        width: 2,
        height: 72,
        displayValue: true,
        fontSize: 16,
        margin: 12,
      });
    } catch {
      /* invalid pattern for encoder */
    }
  }, [open, barcode]);

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
          <Box sx={{ display: "flex", justifyContent: "center", py: 1, overflow: "auto" }}>
            <svg ref={svgRef} />
          </Box>
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
