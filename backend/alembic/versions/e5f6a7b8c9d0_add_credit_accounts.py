"""Add cuentas corrientes (credit accounts): clients, items, payments."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_account_clients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_credit_account_clients_name", "credit_account_clients", ["name"], unique=False
    )

    op.create_table(
        "credit_account_payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["credit_account_clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_credit_account_payments_client_id",
        "credit_account_payments",
        ["client_id"],
        unique=False,
    )

    op.create_table(
        "credit_account_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("settled_unit_price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("settled_line_total", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["credit_account_clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["credit_account_payments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_credit_account_items_client_id",
        "credit_account_items",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_credit_account_items_client_id", table_name="credit_account_items")
    op.drop_table("credit_account_items")
    op.drop_index("ix_credit_account_payments_client_id", table_name="credit_account_payments")
    op.drop_table("credit_account_payments")
    op.drop_index("ix_credit_account_clients_name", table_name="credit_account_clients")
    op.drop_table("credit_account_clients")
