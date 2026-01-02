import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


STEPS = [
    (
        "Great Expectations",
        "ge",
        [sys.executable, "docker/ge/run_expectations.py"],
    ),
    ("Presidio", "presidio", [sys.executable, "docker/presidio/run_presidio.py"]),
    ("SHAP", "shap", [sys.executable, "docker/shap/run_shap.py"]),
    ("ART", "art", [sys.executable, "docker/art/run_art.py"]),
    ("RAGAS", "ragas", [sys.executable, "docker/ragas/run_ragas.py"]),
]

AGGREGATOR_STEP = ("Aggregator", "aggregator", [sys.executable, "docker/aggregator/run_aggregator.py"])


def main() -> None:
    repo_root = Path(__file__).parent
    durations = {}
    pipeline_start = time.perf_counter()
    for label, gate_id, command in STEPS:
        print(f"\n>>> Running {label}")
        started = time.perf_counter()
        result = subprocess.run(command, cwd=repo_root)
        durations[gate_id] = time.perf_counter() - started
        if result.returncode != 0:
            raise SystemExit(f"Step '{label}' failed with exit code {result.returncode}")

    # Run the aggregator once to produce outputs, capturing its runtime.
    label, gate_id, command = AGGREGATOR_STEP
    print(f"\n>>> Running {label}")
    agg_started = time.perf_counter()
    agg_result = subprocess.run(command, cwd=repo_root)
    durations[gate_id] = time.perf_counter() - agg_started
    if agg_result.returncode != 0:
        raise SystemExit(
            f"Step '{label}' failed with exit code {agg_result.returncode}"
        )

    total = time.perf_counter() - pipeline_start

    timings_payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "durations_seconds": durations,
        "total_seconds": total,
    }

    timings_path = repo_root / "reports" / "timings.json"
    timings_path.parent.mkdir(parents=True, exist_ok=True)
    with timings_path.open("w", encoding="utf-8") as f:
        json.dump(timings_payload, f, indent=2)

    # Re-run the aggregator so it can ingest the timings.json payload for the
    # dashboard and consolidated summary files.
    print("\n>>> Refreshing Aggregator with timings")
    refresh_result = subprocess.run(command, cwd=repo_root)
    if refresh_result.returncode != 0:
        raise SystemExit(
            f"Refresh step '{label}' failed with exit code {refresh_result.returncode}"
        )

    print("\nPipeline completed. Aggregated report written to REPORT_SUMMARY.json")
    print("Timings written to", timings_path)


if __name__ == "__main__":
    main()
