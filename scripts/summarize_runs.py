import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
KNOWN_GATES = ["ge", "presidio", "shap", "art", "ragas"]


def load_json(path: Path) -> Optional[Dict[str, object]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def resolve_report_path(path_value: str, run_outputs: Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return run_outputs / candidate


def summarize_gate_metrics(gate: str, report: Optional[Dict[str, object]]) -> str:
    if not report:
        return ""
    if gate == "presidio":
        return f"total_entities={report.get('total_entities')}"
    if gate == "ge":
        return f"expectations={report.get('expectations_count')}"
    if gate == "shap":
        importances = report.get("mean_abs_shap", [])
        if isinstance(importances, list):
            return f"sum_importance={sum(importances):.4f}"
        return ""
    if gate == "art":
        attacks = report.get("attacks", {})
        fgsm = attacks.get("fgsm", {})
        pgd = attacks.get("pgd", {})
        return f"fgsm_adv={fgsm.get('adv_accuracy')},pgd_adv={pgd.get('adv_accuracy')}"
    if gate == "ragas":
        return (
            f"support={report.get('mean_support')},"
            f"coverage={report.get('mean_context_coverage')}"
        )
    return ""


def build_rows(runs_root: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not runs_root.exists():
        return rows

    for metadata_path in runs_root.glob("*/**/scenario_metadata.json"):
        scenario_dir = metadata_path.parent
        run_id = scenario_dir.parent.name
        metadata = load_json(metadata_path) or {}
        scenario = str(metadata.get("scenario", "unknown"))
        run_mode = str(metadata.get("run_mode", "unknown"))
        run_outputs = Path(metadata.get("outputs_root", scenario_dir))
        summary_path = run_outputs / "REPORT_SUMMARY.json"
        summary = load_json(summary_path) or {}

        gate_statuses = {item.get("id"): item for item in summary.get("gate_statuses", [])}
        gate_files = summary.get("gate_status_files", {})

        for gate in KNOWN_GATES:
            status_item = gate_statuses.get(gate)
            status = "skipped"
            evidence_path = ""
            key_metrics = ""
            if status_item:
                status = "pass" if status_item.get("passed") else "fail"
                evidence_path = str(status_item.get("report_path") or gate_files.get(gate, ""))
                report_path = evidence_path
                report = None
                if report_path:
                    report = load_json(resolve_report_path(report_path, run_outputs))
                key_metrics = summarize_gate_metrics(gate, report)

            rows.append(
                {
                    "run_id": run_id,
                    "scenario": scenario,
                    "run_mode": run_mode,
                    "gate": gate,
                    "status": status,
                    "evidence_path": evidence_path,
                    "key_metrics": key_metrics,
                }
            )
    return rows


def write_csv(rows: List[Dict[str, str]], runs_root: Path) -> None:
    runs_root.mkdir(parents=True, exist_ok=True)
    csv_path = runs_root / "summary.csv"
    fieldnames = ["run_id", "scenario", "run_mode", "gate", "status", "evidence_path", "key_metrics"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: List[Dict[str, str]], runs_root: Path) -> None:
    runs_root.mkdir(parents=True, exist_ok=True)
    md_path = runs_root / "summary.md"
    grouped: Dict[str, Dict[str, str]] = {}
    for row in rows:
        key = f"{row['run_id']}:{row['scenario']}"
        grouped.setdefault(key, {"run_id": row["run_id"], "scenario": row["scenario"]})
        grouped[key][row["gate"]] = row["status"]

    headers = ["run_id", "scenario"] + KNOWN_GATES
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for entry in grouped.values():
        status_cells = []
        for gate in KNOWN_GATES:
            status = entry.get(gate, "skipped")
            status_cells.append("✅" if status == "pass" else "❌" if status == "fail" else "—")
        row_cells = [entry["run_id"], entry["scenario"]] + status_cells
        lines.append("| " + " | ".join(row_cells) + " |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize scenario runs under a runs/ directory.")
    parser.add_argument(
        "runs_root",
        nargs="?",
        default="runs",
        help="Runs directory to summarize (default: runs).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runs_root = Path(args.runs_root)
    rows = build_rows(runs_root)
    write_csv(rows, runs_root)
    write_markdown(rows, runs_root)
    print(f"Wrote {runs_root}/summary.csv and {runs_root}/summary.md")


if __name__ == "__main__":
    main()
