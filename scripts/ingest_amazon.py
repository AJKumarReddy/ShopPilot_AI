"""Stream a bounded stratified catalog. Never save complete Amazon source files."""

import argparse
import gzip
import hashlib
import io
import json
import logging
import math
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from app.data.normalization import normalize

LOG = logging.getLogger("ingestion")
SOURCE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_{category}.jsonl.gz"


class StreamReader(io.RawIOBase):
    def __init__(self, chunks: Iterator[bytes]) -> None:
        self.chunks, self.pending = chunks, bytearray()

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        while len(self.pending) < len(buffer):
            chunk = next(self.chunks, None)
            if chunk is None:
                break
            self.pending.extend(chunk)
        count = min(len(buffer), len(self.pending))
        buffer[:count] = self.pending[:count]
        del self.pending[:count]
        return count


def records(url: str) -> Iterator[dict[str, Any]]:
    if not url.startswith("https://"):
        with Path(url).open(encoding="utf-8") as file:
            for line in file:
                yield json.loads(line)
        return
    with (
        httpx.Client(timeout=90, follow_redirects=True) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        raw = io.BufferedReader(StreamReader(response.iter_bytes()), buffer_size=65536)
        stream = gzip.GzipFile(fileobj=raw) if url.endswith(".gz") else raw
        with io.TextIOWrapper(stream, encoding="utf-8") as lines:
            for line in lines:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    LOG.warning("Skipped malformed source record")


def ingest(
    config: dict[str, Any],
    output: Path,
    maximum: int | None = None,
    resume: bool = False,
    source_template: str = SOURCE,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = output.with_suffix(".checkpoint.sqlite")
    if checkpoint.exists() and not resume:
        raise ValueError("Checkpoint exists. Use --resume or choose a new output path.")
    conn = sqlite3.connect(checkpoint)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS selected (id TEXT PRIMARY KEY, category TEXT, subcategory TEXT, priority TEXT, payload TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS progress (category TEXT PRIMARY KEY, scanned INTEGER, rejected INTEGER, duplicates INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS configuration (fingerprint TEXT PRIMARY KEY)"
    )
    fingerprint = hashlib.sha256(
        json.dumps([config, maximum, source_template], sort_keys=True).encode()
    ).hexdigest()
    prior = conn.execute("SELECT fingerprint FROM configuration").fetchone()
    if prior and prior[0] != fingerprint:
        raise ValueError(
            "Resume configuration differs from checkpoint; choose a new output."
        )
    conn.execute("INSERT OR IGNORE INTO configuration VALUES (?)", (fingerprint,))
    conn.commit()
    quotas = config["categories"]
    scale = min(1, maximum / sum(quotas.values())) if maximum else 1
    remaining = maximum or sum(quotas.values())
    for category, requested in quotas.items():
        quota = min(remaining, max(1, math.floor(requested * scale)))
        remaining -= quota
        if quota <= 0:
            continue
        cap = max(1, math.ceil(quota * config["max_subcategory_fraction"]))
        previous = conn.execute(
            "SELECT scanned,rejected,duplicates FROM progress WHERE category=?",
            (category,),
        ).fetchone() or (0, 0, 0)
        offset, rejected, duplicates = previous
        scan_limit = quota * config.get("scan_multiplier", 30)
        if offset >= scan_limit:
            continue
        try:
            for index, raw in enumerate(
                records(source_template.format(category=category)), start=1
            ):
                if index <= offset:
                    continue
                product = normalize(
                    raw, category, config.get("minimum_rating_count", 10)
                )
                if not product:
                    rejected += 1
                elif conn.execute(
                    "SELECT 1 FROM selected WHERE id=?", (product["id"],)
                ).fetchone():
                    duplicates += 1
                else:
                    priority = hashlib.sha256(
                        f"{config['seed']}:{product['id']}".encode()
                    ).hexdigest()
                    if config.get("preferred_terms"):
                        featured = all(
                            term in product["search_text"]
                            for term in config["preferred_terms"]
                        )
                        priority = ("0" if featured else "1") + priority
                    count = conn.execute(
                        "SELECT count(*) FROM selected WHERE category=? AND subcategory=?",
                        (category, product["subcategory"]),
                    ).fetchone()[0]
                    if count >= cap:
                        worst = conn.execute(
                            "SELECT id,priority FROM selected WHERE category=? AND subcategory=? ORDER BY priority DESC LIMIT 1",
                            (category, product["subcategory"]),
                        ).fetchone()
                        if priority < worst[1]:
                            conn.execute("DELETE FROM selected WHERE id=?", (worst[0],))
                        else:
                            product = None
                    if product:
                        conn.execute(
                            "INSERT INTO selected VALUES (?,?,?,?,?)",
                            (
                                product["id"],
                                category,
                                product["subcategory"],
                                priority,
                                json.dumps(product),
                            ),
                        )
                        # Bound the retained category reservoir, including its many strata.
                        conn.execute(
                            "DELETE FROM selected WHERE id IN (SELECT id FROM selected WHERE category=? ORDER BY priority LIMIT -1 OFFSET ?)",
                            (category, quota),
                        )
                conn.execute(
                    "INSERT OR REPLACE INTO progress VALUES (?,?,?,?)",
                    (category, index, rejected, duplicates),
                )
                if index % 500 == 0 or index >= scan_limit:
                    conn.commit()
                    LOG.info(
                        "category=%s scanned=%s selected=%s",
                        category,
                        index,
                        conn.execute(
                            "SELECT count(*) FROM selected WHERE category=?",
                            (category,),
                        ).fetchone()[0],
                    )
                    if (
                        checkpoint.stat().st_size
                        > config.get("max_bytes", 9_000_000_000) // 3
                    ):
                        raise ValueError("Checkpoint size budget reached")
                if index >= scan_limit:
                    break
            conn.commit()
        except Exception:
            conn.commit()
            conn.close()
            raise
    products = [
        json.loads(row[0])
        for row in conn.execute(
            "SELECT payload FROM selected ORDER BY category,priority"
        )
    ]
    stats = conn.execute(
        "SELECT coalesce(sum(rejected),0),coalesce(sum(duplicates),0) FROM progress"
    ).fetchone()
    conn.close()
    temporary = output.with_suffix(output.suffix + ".tmp")
    if output.suffix == ".parquet":
        serializable = [
            {**p, "attributes": json.dumps(p["attributes"])} for p in products
        ]
        pq.write_table(
            pa.Table.from_pylist(serializable), temporary, compression="zstd"
        )
    else:
        with temporary.open("w", encoding="utf-8") as dest:
            for product in products:
                dest.write(json.dumps(product, ensure_ascii=False) + "\n")
    temporary.replace(output)
    from validate_catalog import report

    result = report(products, output, stats[0], stats[1])
    output.with_suffix(".report.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/categories.yaml"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/products.parquet")
    )
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-template", default=SOURCE)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    if args.seed is not None:
        config["seed"] = args.seed
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.dry_run:
        print(
            json.dumps(
                {
                    "config": config,
                    "max_products": args.max_products,
                    "output": str(args.output),
                },
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                ingest(
                    config,
                    args.output,
                    args.max_products,
                    args.resume,
                    args.source_template,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
