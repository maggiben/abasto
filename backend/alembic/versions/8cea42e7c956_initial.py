"""initial

Revision ID: 8cea42e7c956
Revises:
Create Date: 2026-04-02 22:04:01.113793

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "8cea42e7c956"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("cost", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("margin_percent", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("barcode", sa.String(length=128), nullable=True),
        sa.Column("weight_grams", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("is_fractional", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_barcode"), "products", ["barcode"], unique=True)

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("low_stock_threshold", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )

    op.create_table(
        "customer_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("guest_email", sa.String(length=320), nullable=True),
        sa.Column(
            "tracking_token",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("tax_total", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_customer_orders_tracking_token"),
        "customer_orders",
        ["tracking_token"],
        unique=True,
    )

    op.create_table(
        "customer_order_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["customer_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sales",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cashier_user_id", sa.Integer(), nullable=True),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("tax_total", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cashier_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sale_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sale_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "vendor_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_name", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("expected_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "vendor_order_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vendor_order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("quantity_received", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["vendor_order_id"], ["vendor_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("vendor_order_lines")
    op.drop_table("vendor_orders")
    op.drop_table("sale_lines")
    op.drop_table("sales")
    op.drop_table("customer_order_lines")
    op.drop_table("customer_orders")
    op.drop_table("inventory_items")
    op.drop_table("products")
    op.drop_table("users")
