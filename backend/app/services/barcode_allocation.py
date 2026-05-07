"""Internal barcode generation and format checks for product codes."""

from __future__ import annotations

import re
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product

# CODE128-friendly: first char letter/digit; rest may include dot, underscore, hyphen (max 128 chars total).
_BARCODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_MAX_ATTEMPTS = 80
# In-store style numeric codes (12 chars): prefix + 10 random decimal digits.
_INTERNAL_PREFIX = "20"


def validate_barcode_format(value: str) -> None:
    """Raise ValueError if manual barcode is not allowed for scanners / CODE128."""
    if len(value) > 128:
        raise ValueError("Barcode must be at most 128 characters")
    if not _BARCODE_RE.fullmatch(value):
        raise ValueError(
            "Barcode must start with a letter or digit and only contain letters, "
            "digits, dot, underscore, or hyphen",
        )


async def allocate_unique_barcode(session: AsyncSession) -> str:
    """Generate a fresh numeric internal barcode and ensure it is not in use."""
    for _ in range(_MAX_ATTEMPTS):
        n = secrets.randbelow(10**10)
        candidate = f"{_INTERNAL_PREFIX}{n:010d}"
        found = await session.execute(select(Product.id).where(Product.barcode == candidate))
        if found.scalar_one_or_none() is None:
            return candidate
    raise RuntimeError("Could not allocate a unique barcode; try again")
