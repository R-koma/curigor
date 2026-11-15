import json
from pathlib import Path

from evals.dataset import load_source_records
from evals.map_turn_analysis_dataset import DEFAULT_DATASET, load_rows, seed_real_rows


def seed(path: Path = DEFAULT_DATASET) -> int:
    rows = seed_real_rows(load_source_records(), load_rows(path))
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    return len(rows)


def main() -> None:
    print(f"{seed()} 行を足した")


if __name__ == "__main__":
    main()
