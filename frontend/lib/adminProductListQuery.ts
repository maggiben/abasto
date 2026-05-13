import type { GridFilterModel, GridPaginationModel, GridSortModel } from "@mui/x-data-grid";

export type AdminProductListToolbarState = {
  q: string;
  includeInactive: boolean;
  stockHealth: "all" | "low" | "excess";
};

export function gridFieldToSortParam(field: string): string {
  if (field === "stock") return "quantity";
  if (field === "categoryDisplay") return "category";
  if (field === "lowStock") return "low_stock_threshold";
  return field;
}

function strParam(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  return s.length ? s : null;
}

function numParam(v: unknown): string | null {
  if (v === "" || v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(",", "."));
  if (!Number.isFinite(n)) return null;
  return String(n);
}

export function buildAdminProductListSearchParams(
  pagination: GridPaginationModel,
  sortModel: GridSortModel,
  filterModel: GridFilterModel,
  toolbar: AdminProductListToolbarState,
): URLSearchParams {
  const qs = new URLSearchParams();
  qs.set("skip", String(pagination.page * pagination.pageSize));
  qs.set("limit", String(pagination.pageSize));

  const sm = sortModel[0];
  if (sm?.field) {
    qs.set("sort", gridFieldToSortParam(sm.field));
    qs.set("order", sm.sort === "asc" || sm.sort === "desc" ? sm.sort : "desc");
  } else {
    qs.set("sort", "id");
    qs.set("order", "desc");
  }

  const tq = toolbar.q.trim();
  if (tq) qs.set("q", tq);
  if (toolbar.includeInactive) qs.set("include_inactive", "true");
  if (toolbar.stockHealth === "low") qs.set("stock_health", "low");
  else if (toolbar.stockHealth === "excess") qs.set("stock_health", "excess");

  for (const item of filterModel.items) {
    const op = item.operator ?? "";
    const val = item.value;
    const field = item.field;

    if (field === "name") {
      const s = strParam(val);
      if (!s) continue;
      if (op === "contains" || op === "endsWith" || op === "startsWith") qs.set("name_contains", s);
      else if (op === "equals") qs.set("name_exact", s);
    } else if (field === "brand") {
      const s = strParam(val);
      if (!s) continue;
      if (op === "contains" || op === "endsWith" || op === "startsWith") qs.set("brand_contains", s);
      else if (op === "equals") qs.set("brand_exact", s);
    } else if (field === "categoryDisplay") {
      const s = strParam(val);
      if (!s) continue;
      if (op === "contains" || op === "endsWith" || op === "startsWith") qs.set("category_contains", s);
      else if (op === "equals") qs.set("category_exact", s);
    } else if (field === "barcode") {
      const s = strParam(val);
      if (!s) continue;
      if (op === "contains" || op === "endsWith" || op === "startsWith") qs.set("barcode_contains", s);
      else if (op === "equals") qs.set("barcode_exact", s);
    } else if (field === "price") {
      const s = numParam(val);
      if (s === null) continue;
      if (op === ">=") qs.set("price_min", s);
      else if (op === "<=") qs.set("price_max", s);
      else if (op === ">") qs.set("price_gt", s);
      else if (op === "<") qs.set("price_lt", s);
      else if (op === "=") qs.set("price_eq", s);
    } else if (field === "stock" || field === "quantity") {
      const s = numParam(val);
      if (s === null) continue;
      if (op === ">=") qs.set("quantity_min", s);
      else if (op === "<=") qs.set("quantity_max", s);
      else if (op === ">") qs.set("quantity_gt", s);
      else if (op === "<") qs.set("quantity_lt", s);
      else if (op === "=") qs.set("quantity_eq", s);
    } else if (field === "lowStock") {
      const s = numParam(val);
      if (s === null) continue;
      if (op === ">=") qs.set("low_threshold_min", s);
      else if (op === "<=") qs.set("low_threshold_max", s);
      else if (op === ">") qs.set("low_threshold_gt", s);
      else if (op === "<") qs.set("low_threshold_lt", s);
      else if (op === "=") {
        qs.set("low_threshold_min", s);
        qs.set("low_threshold_max", s);
      }
    } else if (field === "is_active" && op === "is") {
      if (val === true) qs.set("is_active", "true");
      else if (val === false) qs.set("is_active", "false");
    }
  }

  return qs;
}
