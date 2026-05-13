const INSUFFICIENT_STOCK = /^Insufficient stock for product (\d+): need (.+), have (.+)$/;

const UNKNOWN_PRODUCT_DETAILS = new Set([
  "Product not found",
  "No active product for this barcode",
]);

/**
 * Maps fixed English API `detail` strings from the backend into localized POS copy.
 * Unknown messages are returned unchanged.
 */
export function translatePosApiDetail(
  detail: string,
  t: (
    key: "apiInsufficientStock" | "productNotInDatabase",
    values?: Record<string, string>,
  ) => string,
): string {
  if (UNKNOWN_PRODUCT_DETAILS.has(detail)) {
    return t("productNotInDatabase");
  }
  const m = detail.match(INSUFFICIENT_STOCK);
  if (m) {
    const [, productId, need, have] = m;
    return t("apiInsufficientStock", {
      productId,
      need: need.trim(),
      have: have.trim(),
    });
  }
  return detail;
}
