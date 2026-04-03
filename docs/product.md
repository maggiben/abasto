# Abasto ERP – Product Specification

## Overview

**Abasto** is a pragmatic ERP designed for small businesses (e.g. grocery stores, kiosks, local shops).

The system prioritizes:
- Speed
- Simplicity
- Low hardware requirements
- Real-world retail workflows (barcode scanners, thermal printers, keyboards)

---

## Core Modules

### 1. POS (Point of Sale)

This is the **most critical part of the system**.

#### Features
- Barcode scanning (keyboard-emulated scanners)
- Add/remove/edit cart items
- Quantity adjustments without rescanning
- Support for fractional products (e.g. 150g cheese)
- Manual price input (for edge cases)
- Product search (keyboard-first)
- “Dry mode” (price check without sale)
- Embedded calculator
- Receipt printing (thermal printer via USB)
- Fast checkout flow (minimal clicks)

#### UX Requirements
- Must be usable with **keyboard only**
- Optimized for **numpad input**
- Large typography and high contrast
- Zero clutter

---

### 2. Inventory Management

#### Features
- Create / edit / delete products
- Bulk and unit inventory tracking
- Fractional product support (weight-based)
- Expiration tracking
- CSV import/export
- Product attributes:
  - Name
  - Price
  - Cost
  - Margin
  - Barcode
  - Weight
  - Expiration date
  - Image (optional)

---

### 3. Orders

#### Customer Orders
- Guest checkout
- Registered users
- Order tracking

#### Vendor Orders
- Purchase tracking
- Restocking workflows

---

### 4. Ecommerce (Web UI)

- Product catalog
- Price & availability display
- Guest checkout
- User registration & login
- Order placement

---

### 5. Admin Panel

#### Features
- Secure login
- Product management
- Inventory audit
- Price/margin editing (single & bulk)
- User management
- Order management
- Delivery planning

---

### 6. Notifications

- Inventory changes
- Low stock alerts
- Expiration alerts
- Orders (customer/vendor)

---

### 7. Analytics & Dashboard

- Sales metrics
- Revenue
- ROI
- Inventory value
- Orders overview
- Time aggregation:
  - Daily
  - Weekly
  - Monthly
  - Yearly

---

### 8. Audit System

- Full activity log
- Track:
  - Inventory changes
  - Price changes
  - Orders
  - User actions

---

### 9. Receipts

Printed via thermal printer.

#### Must include:
- Date & time
- Items
- Quantities
- Total price
- Taxes

---

## Hardware Support

- Barcode scanner (keyboard input)
- Thermal printer (USB, ESC/POS)
- Keyboard-first operation
- Touchscreen optional
