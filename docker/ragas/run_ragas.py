import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def load_jsonl(path: Path) -> List[dict]:
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def main() -> None:
    chunk_path = Path(os.environ.get("RAGAS_CHUNKS", "artifacts/data/rag_chunks/chunks.jsonl"))
    qa_path = Path(os.environ.get("RAGAS_QA", "artifacts/data/qa/qa_set.jsonl"))
    output_detail = Path(os.environ.get("RAGAS_DETAIL", "reports/ragas/per_question.jsonl"))
    output_summary = Path(os.environ.get("RAGAS_SUMMARY", "reports/ragas/summary.json"))

    chunks = load_jsonl(chunk_path)
    qa_items = load_jsonl(qa_path)
    chunk_lookup: Dict[str, dict] = {chunk["id"]: chunk for chunk in chunks}

    per_question_results: List[dict] = []
    support_scores: List[float] = []
    coverage_scores: List[float] = []
    context_counts: List[int] = []

    for qa in qa_items:
        contexts = qa.get("contexts", [])
        context_texts = [chunk_lookup[c]["text"] for c in contexts if c in chunk_lookup]
        answer = (qa.get("answer") or "").lower()
        support = 0.0
        if context_texts and answer:
            support = max(1.0 if answer in text.lower() else 0.0 for text in context_texts)
        coverage = 1.0 if context_texts else 0.0
        support_scores.append(support)
        coverage_scores.append(coverage)
        context_counts.append(len(context_texts))

        per_question_results.append(
            {
                "id": qa.get("id"),
                "question": qa.get("question"),
                "answer": qa.get("answer"),
                "contexts": context_texts,
                "support_score": support,
                "context_coverage": coverage,
            }
        )

    os.makedirs(output_detail.parent, exist_ok=True)
    with output_detail.open("w", encoding="utf-8") as f:
        for record in per_question_results:
            f.write(json.dumps(record) + "\n")

    mean_support = sum(support_scores) / max(len(support_scores), 1)
    mean_coverage = sum(coverage_scores) / max(len(coverage_scores), 1)
    mean_contexts = sum(context_counts) / max(len(context_counts), 1)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "input_chunks": str(chunk_path),
        "input_qa": str(qa_path),
        "total_questions": len(per_question_results),
        "mean_support": mean_support,
        "mean_context_coverage": mean_coverage,
        "mean_contexts_per_question": mean_contexts,
        "threshold_passed": mean_support >= 0.6 and mean_coverage >= 0.6,
    }

    os.makedirs(output_summary.parent, exist_ok=True)
    with output_summary.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
