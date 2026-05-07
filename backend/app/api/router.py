from fastapi import APIRouter

from app.api.routes import (
    admin_analytics,
    admin_audit,
    admin_inventory,
    admin_notifications,
    admin_orders,
    admin_products,
    admin_sales,
    admin_users,
    admin_vendor_orders,
    auth,
    catalog,
    customer_orders,
    health,
    notifications,
    pos,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(customer_orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(pos.router, prefix="/pos", tags=["pos"])
api_router.include_router(admin_products.router, prefix="/admin/products", tags=["admin-products"])
api_router.include_router(admin_inventory.router, prefix="/admin/inventory", tags=["admin-inventory"])
api_router.include_router(admin_orders.router, prefix="/admin/orders", tags=["admin-orders"])
api_router.include_router(admin_sales.router, prefix="/admin/sales", tags=["admin-sales"])
api_router.include_router(admin_vendor_orders.router, prefix="/admin/vendor-orders", tags=["admin-vendor-orders"])
api_router.include_router(admin_audit.router, prefix="/admin/audit-logs", tags=["admin-audit"])
api_router.include_router(admin_analytics.router, prefix="/admin/analytics", tags=["admin-analytics"])
api_router.include_router(admin_notifications.router, prefix="/admin/notifications", tags=["admin-notifications"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"])
