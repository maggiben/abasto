"""add product catalog fields

Revision ID: 2b4a1f7c9d03
Revises: 8cea42e7c956
Create Date: 2026-05-07 17:28:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2b4a1f7c9d03"
down_revision: Union[str, Sequence[str], None] = "8cea42e7c956"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("brand", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("category", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("subcategory", sa.String(length=255), nullable=True))
    op.add_column(
        "products",
        sa.Column("category_detail", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "category_detail")
    op.drop_column("products", "subcategory")
    op.drop_column("products", "category")
    op.drop_column("products", "brand")
