from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.postgres import init_ielts_vocabulary_bank
from backend.services.ielts_vocabulary_bank_service import normalize_word_record, upsert_word_records


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def import_file(path: Path, batch_size: int = 500) -> int:
    init_ielts_vocabulary_bank()
    total_count = sum(1 for _ in iter_jsonl(path))
    imported = 0
    batch = []
    for raw in iter_jsonl(path):
        batch.append(normalize_word_record(raw, total_count=total_count))
        if len(batch) >= batch_size:
            imported += upsert_word_records(batch)
            batch = []
    if batch:
        imported += upsert_word_records(batch)
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Import IELTS vocabulary jsonl into PostgreSQL.")
    parser.add_argument("--file", default="script/IELTSluan_2.jsonl", help="Path to IELTSluan_2.jsonl")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    path = Path(args.file)
    if not path.exists():
        raise FileNotFoundError(path)
    imported = import_file(path, batch_size=max(1, args.batch_size))
    print(f"Imported {imported} vocabulary records into PostgreSQL.")


if __name__ == "__main__":
    main()
