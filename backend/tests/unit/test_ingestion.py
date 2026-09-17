import json
import sys
from pathlib import Path

from app.data.normalization import normalize, synthetic_inventory

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from ingest_amazon import ingest  # noqa: E402


def raw_product(index: int) -> dict[str, object]:
    return {
        "parent_asin": f"ASIN{index}",
        "title": f"Item {index}",
        "price": "29.99",
        "average_rating": 4.4,
        "rating_number": 20,
        "features": ["Durable"],
        "categories": ["Electronics", f"Subcategory{index % 8}"],
        "images": [{"large": "https://example.test/p.jpg"}],
    }


def test_quality_and_inventory_determinism() -> None:
    assert normalize(raw_product(1), "Electronics")
    assert normalize({**raw_product(1), "price": "NaN"}, "Electronics") is None
    assert normalize({**raw_product(1), "rating_number": 2}, "Electronics") is None
    assert synthetic_inventory("id", 1) == synthetic_inventory("id", 1)
    assert synthetic_inventory("id", 1) != synthetic_inventory("id", 2)


def test_ingest_stratification_resume_and_budget(tmp_path: Path) -> None:
    source = tmp_path / "raw.jsonl"
    source.write_text("\n".join(json.dumps(raw_product(i)) for i in range(200)))
    config = {
        "seed": 42,
        "minimum_rating_count": 10,
        "max_subcategory_fraction": 0.2,
        "scan_multiplier": 10,
        "categories": {"Electronics": 20},
        "max_bytes": 10000000,
    }
    output = tmp_path / "products.jsonl"
    report = ingest(config, output, source_template=str(source))
    before = output.read_bytes()
    assert report["total_products"] == 20
    assert max(report["subcategories"].values()) <= 4
    ingest(config, output, resume=True, source_template=str(source))
    assert before == output.read_bytes()
