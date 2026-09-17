import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def load_catalog(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".parquet":
        rows = pq.read_table(path).to_pylist()
        for row in rows:
            if isinstance(row["attributes"], str):
                row["attributes"] = json.loads(row["attributes"])
        return rows
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def distribution(values: list[float]) -> dict[str, float]:
    values.sort()
    if not values:
        return {}
    return {
        "min": values[0],
        "p50": values[len(values) // 2],
        "p95": values[min(len(values) - 1, int(len(values) * 0.95))],
        "max": values[-1],
    }


def report(
    products: list[dict[str, Any]], path: Path, rejected: int = 0, duplicates: int = 0
) -> dict[str, Any]:
    counts = Counter(p["major_category"] for p in products)
    missing = {
        key: sum(not p.get(key) for p in products) / max(1, len(products))
        for key in (
            "title",
            "price",
            "average_rating",
            "rating_count",
            "image_url",
            "external_id",
            "description",
        )
    }
    size = path.stat().st_size
    warnings = []
    if len(products) < 4000:
        warnings.append("Fewer than 4,000 products; appropriate for demo mode only.")
    if size > 10_000_000_000:
        warnings.append("Dataset exceeds 10 GB.")
    if counts and max(counts.values()) > 3 * min(counts.values()):
        warnings.append("Major categories are imbalanced.")
    if any(value > 0.05 for key, value in missing.items() if key != "description"):
        warnings.append("Critical fields have high missing rates.")
    return {
        "total_products": len(products),
        "major_categories": dict(counts),
        "subcategories": dict(
            Counter(f"{p['major_category']}/{p['subcategory']}" for p in products)
        ),
        "missing_field_rates": missing,
        "price_distribution": distribution([float(p["price"]) for p in products]),
        "rating_distribution": distribution(
            [float(p["average_rating"]) for p in products]
        ),
        "rating_count_distribution": distribution(
            [float(p["rating_count"]) for p in products]
        ),
        "rejected_products": rejected,
        "duplicates_removed": duplicates,
        "dataset_bytes": size,
        "warnings": warnings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(report(load_catalog(args.path), args.path), indent=2))
