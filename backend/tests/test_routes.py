from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_includes_auth() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    assert "/catalog/products" in paths
    assert "/catalog/price-check" in paths
    assert "/admin/products" in paths
    assert "/admin/products/{product_id}/permanent" in paths
    assert "/admin/inventory/products/{product_id}" in paths
    assert "/admin/products/export" in paths
    assert "/admin/products/import" in paths
    assert "/admin/products/print-label" in paths
    assert "/pos/checkout" in paths
    assert "/pos/credit-accounts" in paths
    assert "/pos/credit-accounts/charge" in paths
    assert "/orders" in paths
    assert "/orders/me" in paths
    assert "/admin/orders" in paths
    assert "/admin/sales" in paths
    assert "/admin/sales/reset-all" in paths
    assert "/admin/credit-accounts" in paths
    assert "/admin/credit-accounts/{client_id}" in paths
    assert "/admin/credit-accounts/{client_id}/items" in paths
    assert "/admin/credit-accounts/{client_id}/payments" in paths
    assert "/admin/vendor-orders" in paths
    assert "/notifications" in paths
    assert "/notifications/{notification_id}/read" in paths
    assert "/admin/audit-logs" in paths
    assert "/admin/analytics/summary" in paths
    assert "/admin/analytics/top-sellers" in paths
    assert "/admin/notifications" in paths
    assert "/admin/inventory/alerts/low-stock" in paths
    assert "/admin/inventory/alerts/expiring" in paths
    assert "/admin/inventory/alerts/notify-low-stock" in paths
    assert "/admin/audit-logs/export" in paths
    assert "/admin/users/{user_id}/promote" in paths
    assert "/admin/receipt-printer/settings" in paths
    assert "/admin/receipt-printer/test-print" in paths
