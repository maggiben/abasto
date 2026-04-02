#!/usr/bin/env python3

import csv
import sys

CSV_FILE = "products.csv"


def load_db(path):
    db = {}

    # Try latin-1 first (common for these weird chars)
    try:
        f = open(path, encoding="latin-1")
    except Exception as e:
        print(f"Error opening file: {e}")
        sys.exit(1)

    reader = csv.DictReader(f, delimiter=';')

    for row in reader:
        ean = row["ean"].strip()
        db[ean] = {
            "producto": row["producto"],
            "brand": row["brand"],
            "cat1": row["cat1"],
            "cat2": row["cat2"],
            "cat3": row["cat3"],
        }

    f.close()
    return db


def main():
    print("Loading database...")
    db = load_db(CSV_FILE)
    print(f"Loaded {len(db)} products\n")

    print("Ready. Scan a barcode (Ctrl+C to exit):\n")

    while True:
        try:
            ean = input("> ").strip()

            if not ean:
                continue

            product = db.get(ean)

            if product:
                print("\n=== PRODUCT FOUND ===")
                print(f"EAN: {ean}")
                print(f"Name: {product['producto']}")
                print(f"Brand: {product['brand']}")
                print(f"Category: {product['cat1']} > {product['cat2']} > {product['cat3']}")
                print("====================\n")
            else:
                print(f"❌ Not found: {ean}\n")

        except KeyboardInterrupt:
            print("\nBye 👋")
            break


if __name__ == "__main__":
    main()
