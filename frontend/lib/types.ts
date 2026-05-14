export type UserPublic = {
  id: number;
  email: string;
  is_active: boolean;
  is_staff: boolean;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type ProductCatalogItem = {
  id: number;
  name: string;
  price: string;
  tax_rate_percent: string;
  barcode: string | null;
  image_url: string | null;
  is_fractional: boolean;
  quantity: string;
};

export type PriceCheckResponse = {
  product_id: number;
  name: string;
  price: string;
  tax_rate_percent: string;
  barcode: string | null;
  quantity: string;
  is_fractional: boolean;
};

export type InventoryPublic = {
  product_id: number;
  quantity: string;
  low_stock_threshold: string | null;
  updated_at: string;
};

export type ProductWithInventory = {
  id: number;
  name: string;
  description: string | null;
  brand: string | null;
  category: string | null;
  subcategory: string | null;
  category_detail: string | null;
  price: string;
  cost: string | null;
  margin_percent: string | null;
  tax_rate_percent: string;
  barcode: string | null;
  weight_grams: string | null;
  expiration_date: string | null;
  image_url: string | null;
  is_fractional: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  inventory: InventoryPublic | null;
};

export type ProductListPage = {
  items: ProductWithInventory[];
  total: number;
};

export type CheckoutResponse = {
  sale_id: number;
  created_at: string;
  subtotal: string;
  tax_total: string;
  total: string;
  tax_rate_percent: string;
  lines: {
    product_id: number;
    product_name: string;
    quantity: string;
    unit_price: string;
    line_total: string;
  }[];
};

export type Granularity = "day" | "week" | "month" | "year";

export type PresetKey =
  | "7d"
  | "30d"
  | "90d"
  | "this_month"
  | "prev_month"
  | "ytd"
  | "christmas"
  | "holy_week"
  | "custom";

export type AnalyticsTotals = {
  revenue_pos: string;
  revenue_web: string;
  revenue_total: string;
  pos_sale_count: number;
  web_order_count: number;
  inventory_value: string;
  gross_profit: string;
};

export type PeriodBucket = {
  period_start: string;
  revenue_pos: string;
  revenue_web: string;
};

export type AnalyticsSummary = {
  range_start: string;
  range_end: string;
  granularity: "day" | "week" | "month" | "year";
  totals: AnalyticsTotals;
  buckets: PeriodBucket[];
};

export type TopProductRow = {
  product_id: number;
  name: string;
  quantity_sold: string;
  revenue: string;
};

export type TopCategoryRow = {
  category: string;
  quantity_sold: string;
  revenue: string;
};

export type TopSellersOut = {
  products: TopProductRow[];
  categories: TopCategoryRow[];
};

export type ResetSalesOut = {
  pos_tickets_removed: number;
  web_orders_removed: number;
  inventory_restored: boolean;
};

export type ProductCsvImportResult = {
  dry_run: boolean;
  row_count: number;
  created: number;
  updated: number;
};

export type ProductCsvImportStart = {
  job_id: string;
  row_count: number;
  created_estimate: number;
  updated_estimate: number;
};

export type ProductCsvImportStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  row_count: number;
  processed: number;
  created: number;
  updated: number;
  errors: string[];
};

export type ProductBulkDeactivateResult = {
  deactivated: number;
};

export type ReceiptPrinterConfigResolved = {
  store_name: string;
  header_text: string;
  greeting_text: string;
  footer_text: string;
  closing_text: string;
  receipt_locale: "es" | "en";
  show_subtotal: boolean;
  show_tax_lines: boolean;
  include_cashier_on_receipt: boolean;
  feed_lines_before_cut: number;
  logo_base64: string | null;
  logo_max_width: number;
};
