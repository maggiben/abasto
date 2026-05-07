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
  barcode: string | null;
  image_url: string | null;
  is_fractional: boolean;
  quantity: string;
};

export type PriceCheckResponse = {
  product_id: number;
  name: string;
  price: string;
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

export type AnalyticsSummary = {
  totals: {
    revenue_pos: string;
    revenue_web: string;
    revenue_total: string;
    pos_sale_count: number;
    web_order_count: number;
    inventory_value: string;
  };
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
