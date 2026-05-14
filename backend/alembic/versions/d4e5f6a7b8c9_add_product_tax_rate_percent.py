"""Add products.tax_rate_percent (IVA / sales tax per product, default 0)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c7f1a2b3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "tax_rate_percent",
            sa.Numeric(precision=8, scale=4),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "tax_rate_percent")
