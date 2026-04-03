#!/usr/bin/env python3
"""Print a receipt from JSON on stdin (same shape as POST /pos/checkout response).

Examples:
  python scripts/print_receipt.py < receipt.json
  python scripts/print_receipt.py --force < receipt.json

Requires optional deps: pip install -e ".[printer]"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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
    from app.services.receipt_printer import try_print_receipt

    data = json.load(sys.stdin)
    checkout = CheckoutResponse.model_validate(data)
    settings = get_settings()
    try_print_receipt(
        settings,
        checkout,
        cashier_email=data.get("_cashier_email"),
        force=args.force,
    )


if __name__ == "__main__":
    main()
