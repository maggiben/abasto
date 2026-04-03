from enum import StrEnum


class CustomerOrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class VendorOrderStatus(StrEnum):
    DRAFT = "draft"
    ORDERED = "ordered"
    PARTIAL = "partial"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class NotificationType(StrEnum):
    INVENTORY_CHANGE = "inventory_change"
    LOW_STOCK = "low_stock"
    EXPIRATION = "expiration"
    ORDER_CUSTOMER = "order_customer"
    ORDER_VENDOR = "order_vendor"
