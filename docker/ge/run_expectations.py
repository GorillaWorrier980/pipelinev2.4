import csv
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List


DATE_FIELDS = {"sent_at": "%Y-%m-%d %H:%M:%S"}
BOOLEAN_TRUE = {"true", "false", "True", "False", True, False}


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def expectation_not_null(rows: List[Dict[str, str]], column: str) -> Dict[str, object]:
    missing = [idx for idx, row in enumerate(rows, start=1) if row.get(column) in (None, "")]
    return {
        "name": f"{column}_not_null",
        "success": not missing,
        "details": {"missing_rows": missing},
    }


def expectation_unique(rows: List[Dict[str, str]], column: str) -> Dict[str, object]:
    counter = Counter(row.get(column) for row in rows)
    duplicates = [value for value, count in counter.items() if count > 1]
    return {
        "name": f"{column}_unique",
        "success": not duplicates,
        "details": {"duplicate_values": duplicates},
    }


def expectation_date_format(rows: List[Dict[str, str]], column: str, fmt: str) -> Dict[str, object]:
    invalid = []
    for idx, row in enumerate(rows, start=1):
        value = row.get(column)
        if not value:
            invalid.append({"row": idx, "value": value})
            continue
        try:
            datetime.strptime(value, fmt)
        except ValueError:
            invalid.append({"row": idx, "value": value})
    return {
        "name": f"{column}_format_{fmt}",
        "success": not invalid,
        "details": {"invalid": invalid},
    }


def expectation_allowed_values(rows: List[Dict[str, str]], column: str, allowed) -> Dict[str, object]:
    invalid = []
    for idx, row in enumerate(rows, start=1):
        value = row.get(column)
        if value not in allowed:
            invalid.append({"row": idx, "value": value})
    return {
        "name": f"{column}_allowed_values",
        "success": not invalid,
        "details": {"invalid": invalid, "allowed": sorted({str(v) for v in allowed})},
    }


def main() -> None:
    input_path = Path(os.environ.get("GE_INPUT", "artifacts/data/tabular/tabular_enron.csv"))
    output_path = Path(os.environ.get("GE_OUTPUT", "reports/ge/summary.json"))

    rows = load_rows(input_path)
    columns = rows[0].keys() if rows else []

    expectations: List[Dict[str, object]] = []
    for column in columns:
        expectations.append(expectation_not_null(rows, column))
        if column in DATE_FIELDS:
            expectations.append(expectation_date_format(rows, column, DATE_FIELDS[column]))
    if "message_id" in columns:
        expectations.append(expectation_unique(rows, "message_id"))
    if "has_attachment" in columns:
        expectations.append(expectation_allowed_values(rows, "has_attachment", BOOLEAN_TRUE))

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "input_path": str(input_path),
        "row_count": len(rows),
        "columns": list(columns),
        "expectations": expectations,
        "success": all(item["success"] for item in expectations),
    }

    os.makedirs(output_path.parent, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


if __name__ == "__main__":
    main()
