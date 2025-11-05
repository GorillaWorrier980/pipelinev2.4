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


def evaluate_ge(report):
    if not report:
        return False, "Report missing"
    if report.get("success"):
        passed_expectations = len(report.get("expectations", []))
        return True, f"All {passed_expectations} expectations passed"
    failed = [item.get("name") for item in report.get("expectations", []) if not item.get("success")]
    if failed:
        return False, "Failed expectations: " + ", ".join(failed[:5])
    return False, "Missing expectation details"


def evaluate_presidio(report):
    if not report:
        return False, "Report missing"
    total_hits = sum(report.get("entity_counts", {}).values())
    if total_hits > 0:
        return True, f"Detected {total_hits} entities"
    return False, "No PII entities detected"


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
    if report.get("threshold_passed"):
        score = report.get("mean_support", 0.0)
        return True, f"Mean support {score:.2f} >= 0.60"
    score = report.get("mean_support")
    if score is None:
        return False, "Missing mean support"
    return False, f"Mean support {score:.2f} below 0.60"


def evaluate_trivy(report):
    if not report:
        return False, "Report missing"
    summary = report.get("severity_summary", {})
    critical = int(summary.get("CRITICAL", 0))
    high = int(summary.get("HIGH", 0))
    if critical == 0 and high == 0:
        return True, "No HIGH or CRITICAL vulnerabilities"
    return False, f"HIGH/CRITICAL findings: {critical + high}"


GATE_RULES = {
    "ge": {
        "label": "Great Expectations",
        "pass_criteria": "All configured expectations must succeed.",
        "evaluator": evaluate_ge,
    },
    "presidio": {
        "label": "Presidio",
        "pass_criteria": "At least one PII entity is detected in the sample.",
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
        "pass_criteria": "Mean support score meets or exceeds the 0.60 threshold.",
        "evaluator": evaluate_ragas,
    },
    "trivy": {
        "label": "Trivy",
        "pass_criteria": "No HIGH or CRITICAL vulnerabilities are present in the scan.",
        "evaluator": evaluate_trivy,
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


def build_gate_statuses(summary):
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

    gate_statuses = build_gate_statuses(summary)
    summary["gate_statuses"] = gate_statuses
    summary["dashboard"] = {"path": str(dashboard_path)}

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
    print("Available reports:", available)
    print("Missing reports:", missing)
    print("Passed gates:", passed)
    print("Failed gates:", failed)


if __name__ == "__main__":
    main()
