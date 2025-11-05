import json
import os
from datetime import datetime
from pathlib import Path


REPORT_PATHS = {
    "ge": "reports/ge/summary.json",
    "presidio": "reports/presidio/redaction_summary.json",
    "shap": "reports/shap/global.json",
    "art": "reports/art/robustness.json",
    "ragas": "reports/ragas/summary.json",
    "trivy": "reports/trivy/cve.json",
}


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def main() -> None:
    output_path = Path(os.environ.get("AGGREGATOR_OUTPUT", "REPORT_SUMMARY.json"))

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "reports": {},
        "missing_reports": [],
    }

    for name, relative_path in REPORT_PATHS.items():
        report_path = Path(os.environ.get(f"REPORT_{name.upper()}", relative_path))
        data = load_json(report_path)
        if data is None:
            summary["missing_reports"].append(str(report_path))
        else:
            summary["reports"][name] = data

    os.makedirs(output_path.parent, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Echo a concise snapshot so CI logs show where the outputs live.
    available = ", ".join(sorted(summary["reports"].keys())) or "(none)"
    missing = ", ".join(summary["missing_reports"]) or "(none)"
    print("Aggregator wrote consolidated report to", output_path)
    print("Available reports:", available)
    print("Missing reports:", missing)


if __name__ == "__main__":
    main()
