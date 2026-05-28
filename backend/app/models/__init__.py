"""ORM models (import side effects register tables on Base.metadata)."""

from app.models.audit import AuditLog
from app.models.credit_account import (
    CreditAccountClient,
    CreditAccountItem,
    CreditAccountPayment,
)
from app.models.notification import Notification
from app.models.order import CustomerOrder, CustomerOrderLine, Sale, SaleLine
from app.models.product import InventoryItem, Product
from app.models.user import User
from app.models.receipt_printer_settings import ReceiptPrinterSettings
from app.models.vendor_order import VendorOrder, VendorOrderLine

__all__ = [
    "AuditLog",
    "CreditAccountClient",
    "CreditAccountItem",
    "CreditAccountPayment",
    "CustomerOrder",
    "CustomerOrderLine",
    "InventoryItem",
    "Notification",
    "Product",
    "ReceiptPrinterSettings",
    "Sale",
    "SaleLine",
    "User",
    "VendorOrder",
    "VendorOrderLine",
]
