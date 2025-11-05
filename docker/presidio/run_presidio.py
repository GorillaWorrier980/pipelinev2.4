import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List


EMAIL_PATTERN = re.compile(r"[\w.%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d -]{7,}\d)\b")
NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")
NAME_STOPWORDS = {"Q2", "Team", "Project", "Results", "HQ"}


def load_records(path: Path) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def detect_entities(text: str) -> Iterable[Dict[str, str]]:
    for match in EMAIL_PATTERN.finditer(text):
        yield {"entity": "EMAIL", "value": match.group(0), "span": match.span()}
    for match in PHONE_PATTERN.finditer(text):
        yield {"entity": "PHONE", "value": match.group(0), "span": match.span()}
    for match in NAME_PATTERN.finditer(text):
        value = match.group(1)
        if any(token in NAME_STOPWORDS for token in value.split()):
            continue
        yield {"entity": "NAME", "value": value, "span": match.span(1)}


def main() -> None:
    input_path = Path(os.environ.get("PRESIDIO_INPUT", "artifacts/data/text/enron_text.jsonl"))
    output_path = Path(os.environ.get("PRESIDIO_OUTPUT", "reports/presidio/redaction_summary.json"))

    records = load_records(input_path)
    entity_counter: Counter[str] = Counter()
    redacted_examples: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for record in records:
        text = f"{record.get('subject', '')}\n{record.get('body', '')}"
        for entity in detect_entities(text):
            entity_type = entity["entity"]
            entity_counter[entity_type] += 1
            if len(redacted_examples[entity_type]) < 3:
                redacted_examples[entity_type].append(
                    {
                        "message_id": record.get("message_id"),
                        "original": entity["value"],
                        "redacted": f"<{entity_type}>",
                    }
                )

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "input_path": str(input_path),
        "entity_counts": dict(entity_counter),
        "examples": {key: value for key, value in redacted_examples.items()},
    }

    os.makedirs(output_path.parent, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


if __name__ == "__main__":
    main()
