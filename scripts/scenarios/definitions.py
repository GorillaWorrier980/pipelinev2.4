import csv
import json
import random
from pathlib import Path
from typing import Dict, List


def apply_data_quality_degradation(input_root: Path, ratio: float) -> Dict[str, object]:
    csv_path = input_root / "artifacts" / "data" / "tabular" / "tabular_enron.csv"
    rows: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)

    if not rows:
        return {"row_ratio": ratio, "mutated_rows": 0}

    rng = random.Random(0)
    count = max(1, int(len(rows) * ratio))
    indices = rng.sample(range(len(rows)), k=min(count, len(rows)))
    for idx in indices:
        rows[idx]["sender"] = ""
        rows[idx]["sent_at"] = "not-a-date"
        rows[idx]["has_attachment"] = "maybe"
        rows[idx]["message_id"] = rows[0]["message_id"]

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return {"row_ratio": ratio, "mutated_rows": len(indices), "csv_path": str(csv_path)}


def apply_pii_injection(input_root: Path, ratio: float) -> Dict[str, object]:
    jsonl_path = input_root / "artifacts" / "data" / "text" / "enron_text.jsonl"
    records = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        return {"row_ratio": ratio, "mutated_rows": 0}

    rng = random.Random(1)
    count = max(1, int(len(records) * ratio))
    indices = rng.sample(range(len(records)), k=min(count, len(records)))
    injection = "Contact Jane Doe at jane.doe@example.com or 415-555-0134."
    for idx in indices:
        subject = records[idx].get("subject", "")
        body = records[idx].get("body", "")
        records[idx]["subject"] = f"{subject} [PII]"
        records[idx]["body"] = f"{body}\n{injection}"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    return {"row_ratio": ratio, "mutated_rows": len(indices), "jsonl_path": str(jsonl_path)}


def apply_explainability_shift(input_root: Path) -> Dict[str, object]:
    weights_path = input_root / "artifacts" / "models" / "classifier" / "shap_shift_weights.json"
    payload = {"weights": [], "bias": []}
    weights_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"weights_path": str(weights_path), "mode": "empty"}


def apply_robustness_drop(input_root: Path) -> Dict[str, object]:
    weights_path = input_root / "artifacts" / "models" / "classifier" / "robustness_drop_weights.json"
    weights = [[0.0 for _ in range(16)] for _ in range(10)]
    payload = {"weights": weights, "bias": [0.0 for _ in range(10)]}
    weights_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"weights_path": str(weights_path), "mode": "zeros"}
