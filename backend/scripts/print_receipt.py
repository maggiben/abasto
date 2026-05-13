#!/usr/bin/env python3
"""Print a receipt from JSON on stdin (same shape as POST /pos/checkout response).

Examples:
  python scripts/print_receipt.py < receipt.json
  python scripts/print_receipt.py --force < receipt.json

Requires optional deps: pip install -e ".[printer]"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


async def _load_layout():
    from app.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.services.receipt_printer_config import load_resolved_receipt_layout

    settings = get_settings()
    async with AsyncSessionLocal() as session:
        return await load_resolved_receipt_layout(session, settings)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    parser = argparse.ArgumentParser(description="Print POS receipt JSON to USB thermal printer")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Print even if PRINTER_ENABLED is false in .env",
    )
    args = parser.parse_args()

    from app.config import get_settings
    from app.schemas.sale import CheckoutResponse
    from app.services.receipt_printer import send_receipt_to_printer
    from app.services.receipt_printer_config import default_resolved_layout

    data = json.load(sys.stdin)
    checkout = CheckoutResponse.model_validate(data)
    settings = get_settings()
    try:
        layout = asyncio.run(_load_layout())
    except Exception:
        layout = default_resolved_layout(settings)
    send_receipt_to_printer(
        settings,
        checkout,
        layout,
        cashier_email=data.get("_cashier_email"),
        force=args.force,
        is_test=False,
    )


if __name__ == "__main__":
    main()
