import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from devaisecops.config import get_config, resolve_enabled_gates


REPORT_PATHS = {
    "ge": "reports/ge/summary.json",
    "presidio": "reports/presidio/redaction_summary.json",
    "shap": "reports/shap/global.json",
    "art": "reports/art/robustness.json",
    "ragas": "reports/ragas/summary.json",
}

DEFAULT_TIMINGS_PATH = "reports/timings.json"


def evaluate_ge(report, thresholds):
    if not report:
        return False, "Report missing"
    expectations = report.get("expectations") or []
    total = len(expectations)
    failed = [item.get("name") for item in expectations if not item.get("success")]
    passed_count = total - len(failed)

    row_count = report.get("row_count", 0)
    columns = report.get("columns") or []

    minimum = thresholds.get("min_expectations", 1)
    if total < minimum:
        return (
            False,
            f"GE report declared {total} expectations; verify headers/rows "
            f"(rows: {row_count}, columns: {len(columns)})",
        )

    if report.get("success"):
        return True, f"All {total} expectations passed"
    if failed:
        return False, f"{len(failed)} of {total} expectations failed: " + ", ".join(failed[:5])
    return False, f"{passed_count}/{total} expectations passed"


def evaluate_presidio(report, thresholds):
    if not report:
        return False, "Report missing"
    if "total_entities" in report:
        total_hits = report.get("total_entities", 0)
    else:
        total_hits = sum(report.get("entity_counts", {}).values())
    max_entities = thresholds.get("max_total_entities", 0)
    if total_hits > max_entities:
        return False, f"Detected {total_hits} entities (max allowed {max_entities})"
    return True, "No PII detected"


def evaluate_shap(report, thresholds):
    if not report:
        return False, "Report missing"
    importances = report.get("mean_abs_shap", [])
    if not importances:
        return False, "Missing importance scores"
    total = sum(importances)
    target = thresholds.get("sum_target", 1.0)
    tolerance = thresholds.get("tolerance", 0.01)
    if abs(total - target) <= tolerance:
        return True, "Importance scores normalized"
    return False, f"Scores sum to {total:.2f}"


def evaluate_art(report, thresholds):
    if not report:
        return False, "Report missing"
    attacks = report.get("attacks", {})
    failing = []
    min_adv = thresholds.get("min_adv_accuracy", 0.7)
    for name, payload in attacks.items():
        adv_acc = payload.get("adv_accuracy")
        if adv_acc is None or adv_acc < min_adv:
            failing.append(f"{name}: {adv_acc}")
    if failing:
        return False, "Low adversarial accuracy for " + ", ".join(failing)
    return True, f"All adversarial accuracies >= {min_adv:.2f}"


def evaluate_ragas(report, thresholds):
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

    min_support = thresholds.get("min_support", 0.6)
    min_coverage = thresholds.get("min_coverage", 0.6)
    passed = (mean_support >= min_support) and (mean_coverage >= min_coverage)
    detail = (
        f"Support {mean_support:.2f}, coverage {mean_coverage:.2f}, "
        f"contexts/question {mean_contexts:.2f}"
    )
    if passed:
        return True, detail + " (support/coverage thresholds met)"
    return False, detail + f" (support or coverage below {min_support:.2f})"


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


def build_gate_statuses(summary, resolved_paths, durations, thresholds, enabled_gates):
    statuses = []
    for gate, config in GATE_RULES.items():
        if gate not in enabled_gates:
            continue
        report = summary["reports"].get(gate)
        gate_thresholds = thresholds.get(gate, {})
        passed, details = config["evaluator"](report, gate_thresholds)
        duration = durations.get(gate)
        statuses.append(
            {
                "id": gate,
                "label": config["label"],
                "passed": passed,
                "details": details,
                "pass_criteria": config["pass_criteria"],
                "report_path": str(resolved_paths.get(gate, "")),
                "duration_seconds": duration,
            }
        )
    return statuses


def render_dashboard(statuses, generated_at):
    rows = []
    for status in statuses:
        badge = "✅" if status["passed"] else "❌"
        duration_cell = (
            f"{status['duration_seconds']:.2f}s" if status.get("duration_seconds") else "—"
        )
        rows.append(
            "            <tr>"
            f"<td>{status['label']}</td>"
            f"<td>{badge}</td>"
            f"<td>{status['pass_criteria']}</td>"
            f"<td>{status['details']} ({duration_cell})</td>"
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
    config_path = os.environ.get("PIPELINE_CONFIG")
    pipeline_config = get_config(config_path) if config_path else get_config()
    enabled_gates, _ = resolve_enabled_gates(pipeline_config)
    enabled_gates_set = set(enabled_gates) if enabled_gates else set(GATE_RULES.keys())
    thresholds = pipeline_config.get("thresholds", {})
    output_path = Path(os.environ.get("AGGREGATOR_OUTPUT", "REPORT_SUMMARY.json"))
    dashboard_path = Path(os.environ.get("DASHBOARD_OUTPUT", "reports/dashboard/index.html"))
    gate_status_dir = Path(
        os.environ.get("DASHBOARD_GATES_DIR", "reports/dashboard/gates")
    )

    timings_path = Path(os.environ.get("AGGREGATOR_TIMINGS", DEFAULT_TIMINGS_PATH))

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "reports": {},
        "missing_reports": [],
    }

    resolved_paths = {}
    for name, relative_path in REPORT_PATHS.items():
        if name not in enabled_gates_set:
            continue
        report_path = Path(os.environ.get(f"REPORT_{name.upper()}", relative_path))
        resolved_paths[name] = report_path
        data = load_json(report_path)
        if data is None:
            summary["missing_reports"].append(str(report_path))
        else:
            summary["reports"][name] = data

    durations = {}
    total_duration = None
    if timings_path.exists():
        timings_payload = load_json(timings_path) or {}
        if isinstance(timings_payload, dict):
            durations = timings_payload.get("durations_seconds", {}) or {}
            total_duration = timings_payload.get("total_seconds")

    gate_statuses = build_gate_statuses(summary, resolved_paths, durations, thresholds, enabled_gates_set)
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
    summary["durations_seconds"] = durations
    if total_duration is not None:
        summary["total_duration_seconds"] = total_duration
    if timings_path.exists():
        summary["timings_path"] = str(timings_path)

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

    if durations:
        parts = []
        for gate_id, value in sorted(durations.items()):
            parts.append(f"{gate_id}={value:.2f}s")
        print("Gate durations:", ", ".join(parts))
    if total_duration is not None:
        print(f"Total pipeline duration: {total_duration:.2f}s")


if __name__ == "__main__":
    main()
