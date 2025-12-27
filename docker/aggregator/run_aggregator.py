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
}


def evaluate_ge(report):
    if not report:
        return False, "Report missing"
    expectations = report.get("expectations") or []
    total = len(expectations)
    failed = [item.get("name") for item in expectations if not item.get("success")]
    passed_count = total - len(failed)

    row_count = report.get("row_count")
    columns = report.get("columns") or []

    # Treat a zero-expectation report as a failure with an actionable message so
    # the dashboard never shows the vague "No expectations were evaluated" text.
    if total == 0:
        return (
            False,
            "GE report contained zero expectations (rows: "
            f"{row_count}, columns: {len(columns)})",
        )

    if report.get("success"):
        return True, f"All {total} expectations passed"
    if failed:
        return False, f"{len(failed)} of {total} expectations failed: " + ", ".join(failed[:5])
    return False, f"{passed_count}/{total} expectations passed"


def evaluate_presidio(report):
    if not report:
        return False, "Report missing"
    if "total_entities" in report:
        total_hits = report.get("total_entities", 0)
    else:
        total_hits = sum(report.get("entity_counts", {}).values())
    if total_hits > 0:
        return False, f"Detected {total_hits} entities (policy blocks any PII)"
    return True, "No PII detected"


def evaluate_shap(report):
    if not report:
        return False, "Report missing"
    importances = report.get("mean_abs_shap", [])
    if not importances:
        return False, "Missing importance scores"
    total = sum(importances)
    if abs(total - 1.0) <= 0.01:
        return True, "Importance scores normalized"
    return False, f"Scores sum to {total:.2f}"


def evaluate_art(report):
    if not report:
        return False, "Report missing"
    attacks = report.get("attacks", {})
    failing = []
    for name, payload in attacks.items():
        adv_acc = payload.get("adv_accuracy")
        if adv_acc is None or adv_acc < 0.7:
            failing.append(f"{name}: {adv_acc}")
    if failing:
        return False, "Low adversarial accuracy for " + ", ".join(failing)
    return True, "All adversarial accuracies >= 0.70"


def evaluate_ragas(report):
    if not report:
        return False, "Report missing"
    mean_support = report.get("mean_support")
    mean_coverage = report.get("mean_context_coverage")
    mean_contexts = report.get("mean_contexts_per_question")

    metrics_missing = [
        name
        for name, value in [
            ("support", mean_support),
            ("coverage", mean_coverage),
            ("contexts", mean_contexts),
        ]
        if value is None
    ]
    if metrics_missing:
        return False, "Missing metrics: " + ", ".join(metrics_missing)

    passed = (mean_support >= 0.6) and (mean_coverage >= 0.6)
    detail = (
        f"Support {mean_support:.2f}, coverage {mean_coverage:.2f}, "
        f"contexts/question {mean_contexts:.2f}"
    )
    if passed:
        return True, detail + " (support/coverage thresholds met)"
    return False, detail + " (support or coverage below 0.60)"


GATE_RULES = {
    "ge": {
        "label": "Great Expectations",
        "pass_criteria": "All configured expectations must succeed.",
        "evaluator": evaluate_ge,
    },
    "presidio": {
        "label": "Presidio",
        "pass_criteria": "No PII entities should be detected; any hit fails.",
        "evaluator": evaluate_presidio,
    },
    "shap": {
        "label": "SHAP",
        "pass_criteria": "Global importance scores should sum to 1.0 (±0.01).",
        "evaluator": evaluate_shap,
    },
    "art": {
        "label": "ART",
        "pass_criteria": "Adversarial accuracies for FGSM and PGD stay at or above 0.70.",
        "evaluator": evaluate_art,
    },
    "ragas": {
        "label": "RAGAS",
        "pass_criteria": "Both support and context coverage averages must be >= 0.60.",
        "evaluator": evaluate_ragas,
    },
}


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def build_gate_statuses(summary, resolved_paths):
    statuses = []
    for gate, config in GATE_RULES.items():
        report = summary["reports"].get(gate)
        passed, details = config["evaluator"](report)
        statuses.append(
            {
                "id": gate,
                "label": config["label"],
                "passed": passed,
                "details": details,
                "pass_criteria": config["pass_criteria"],
                "report_path": str(resolved_paths.get(gate, "")),
            }
        )
    return statuses


def render_dashboard(statuses, generated_at):
    rows = []
    for status in statuses:
        badge = "✅" if status["passed"] else "❌"
        rows.append(
            "            <tr>"
            f"<td>{status['label']}</td>"
            f"<td>{badge}</td>"
            f"<td>{status['pass_criteria']}</td>"
            f"<td>{status['details']}</td>"
            "</tr>"
        )
    table_rows = "\n".join(rows) if rows else "            <tr><td colspan=4>No gate results found.</td></tr>"
    return f"""<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Quality Gates Dashboard</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f5f7fa; }}
      h1 {{ margin-bottom: 0.25rem; }}
      .timestamp {{ color: #555; margin-bottom: 1.5rem; }}
      table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
      th, td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #e0e6ed; vertical-align: top; }}
      th {{ text-align: left; background: #f0f3f7; font-weight: 600; }}
      tr:last-child td {{ border-bottom: none; }}
    </style>
  </head>
  <body>
    <h1>Quality Gates Dashboard</h1>
    <div class=\"timestamp\">Generated at {generated_at}</div>
    <table>
      <thead>
        <tr>
          <th>Gate</th>
          <th>Status</th>
          <th>Pass Criteria</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
{table_rows}
      </tbody>
    </table>
  </body>
</html>
"""


def main() -> None:
    output_path = Path(os.environ.get("AGGREGATOR_OUTPUT", "REPORT_SUMMARY.json"))
    dashboard_path = Path(os.environ.get("DASHBOARD_OUTPUT", "reports/dashboard/index.html"))
    gate_status_dir = Path(
        os.environ.get("DASHBOARD_GATES_DIR", "reports/dashboard/gates")
    )

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "reports": {},
        "missing_reports": [],
    }

    resolved_paths = {}
    for name, relative_path in REPORT_PATHS.items():
        report_path = Path(os.environ.get(f"REPORT_{name.upper()}", relative_path))
        resolved_paths[name] = report_path
        data = load_json(report_path)
        if data is None:
            summary["missing_reports"].append(str(report_path))
        else:
            summary["reports"][name] = data

    gate_statuses = build_gate_statuses(summary, resolved_paths)
    os.makedirs(gate_status_dir, exist_ok=True)

    gate_status_files = {}
    for status in gate_statuses:
        status_path = gate_status_dir / f"{status['id']}.json"
        payload = {
            "id": status["id"],
            "label": status["label"],
            "passed": status["passed"],
            "details": status["details"],
            "pass_criteria": status["pass_criteria"],
            "report_path": status["report_path"],
            "generated_at": summary["generated_at"],
        }
        with status_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        gate_status_files[status["id"]] = str(status_path)
        status["status_report"] = str(status_path)

    summary["gate_statuses"] = gate_statuses
    summary["dashboard"] = {"path": str(dashboard_path)}
    summary["gate_status_files"] = gate_status_files

    os.makedirs(output_path.parent, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    os.makedirs(dashboard_path.parent, exist_ok=True)
    dashboard_html = render_dashboard(gate_statuses, summary["generated_at"])
    with dashboard_path.open("w", encoding="utf-8") as f:
        f.write(dashboard_html)

    # Echo a concise snapshot so CI logs show where the outputs live.
    available = ", ".join(sorted(summary["reports"].keys())) or "(none)"
    missing = ", ".join(summary["missing_reports"]) or "(none)"
    passed = ", ".join(status["id"] for status in gate_statuses if status["passed"]) or "(none)"
    failed = ", ".join(status["id"] for status in gate_statuses if not status["passed"]) or "(none)"
    print("Aggregator wrote consolidated report to", output_path)
    print("Dashboard available at", dashboard_path)
    print("Gate status JSON directory:", gate_status_dir)
    print("Available reports:", available)
    print("Missing reports:", missing)
    print("Passed gates:", passed)
    print("Failed gates:", failed)


if __name__ == "__main__":
    main()
