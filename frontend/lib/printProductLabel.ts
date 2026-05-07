import JsBarcode from "jsbarcode";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const BARCODE_OK = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

export function isValidManualBarcode(value: string): boolean {
  const t = value.trim();
  if (!t) return true;
  return BARCODE_OK.test(t);
}

/** Opens the browser print dialog with the product name and a CODE128 barcode. Returns false if pop-ups blocked or encoding fails. */
export function printProductLabel(productName: string, barcodeValue: string): boolean {
  const trimmed = barcodeValue.trim();
  if (!trimmed) return false;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  try {
    JsBarcode(svg, trimmed, {
      format: "CODE128",
      width: 2,
      height: 72,
      displayValue: true,
      fontSize: 16,
      margin: 12,
    });
  } catch {
    return false;
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Label</title>
<style>
  body { margin: 0; padding: 16px; font-family: system-ui, sans-serif; text-align: center; }
  .name { font-size: 15px; font-weight: 600; margin-bottom: 10px; word-break: break-word; max-width: 82mm; margin-left: auto; margin-right: auto; line-height: 1.25; }
  svg { max-width: 100%; height: auto; }
</style>
</head>
<body>
  <div class="name">${escapeHtml(productName)}</div>
  ${svg.outerHTML}
</body>
</html>`;

  const w = window.open("", "_blank");
  if (!w) return false;
  w.document.open();
  w.document.write(html);
  w.document.close();
  window.setTimeout(() => {
    w.focus();
    w.print();
    w.close();
  }, 250);
  return true;
}
