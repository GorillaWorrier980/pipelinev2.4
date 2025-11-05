import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine


def load_records(path: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def main() -> None:
    input_path = os.environ.get("PRESIDIO_INPUT", "artifacts/data/text/enron_text.jsonl")
    output_path = os.environ.get("PRESIDIO_OUTPUT", "reports/presidio/redaction_summary.json")

    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    records = load_records(input_path)
    entity_counter: Counter[str] = Counter()
    redacted_examples: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for record in records:
        text = f"{record.get('subject', '')}\n{record.get('body', '')}"
        results = analyzer.analyze(text=text, language="en")
        if not results:
            continue
        for result in results:
            entity_counter[result.entity_type] += 1

        anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={result.entity_type: {"type": "replace", "new_value": f"<{result.entity_type}>"} for result in results},
        )

        for result in results:
            if len(redacted_examples[result.entity_type]) < 3:
                redacted_examples[result.entity_type].append(
                    {
                        "message_id": record.get("message_id"),
                        "original": text[result.start : result.end],
                        "redacted": f"<{result.entity_type}>",
                    }
                )

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "input_path": input_path,
        "entity_counts": dict(entity_counter),
        "examples": {key: value for key, value in redacted_examples.items()},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
