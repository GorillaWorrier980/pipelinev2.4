import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from devaisecops.config import get_config, resolve_enabled_gates


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the DevAI SecOps pipeline.")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a pipeline config JSON file.",
    )
    parser.add_argument(
        "--gates",
        default=None,
        help="Comma-separated gate list to override enabled_gates.",
    )
    parser.add_argument(
        "--no-aggregate",
        action="store_true",
        help="Skip aggregator and timing refresh steps.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="No-op placeholder for compatibility with CI scripts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pipeline_config = get_config(args.config) if args.config else get_config()
    override_gates = None
    if args.gates:
        override_gates = [item.strip() for item in args.gates.split(",") if item.strip()]
    enabled_gates, unknown = resolve_enabled_gates(pipeline_config, override_gates)
    enabled_set = set(enabled_gates) if enabled_gates else {gate_id for _, gate_id, _ in STEPS}

    if unknown:
        print(f"Warning: unknown gates requested: {', '.join(unknown)}", file=sys.stderr)

    repo_root = REPO_ROOT
    durations = {}
    pipeline_start = time.perf_counter()

    env = os.environ.copy()
    if args.config:
        env["PIPELINE_CONFIG"] = args.config

    for label, gate_id, command in STEPS:
        if gate_id not in enabled_set:
            print(f"\n>>> Skipping {label} (disabled)")
            continue
        print(f"\n>>> Running {label}")
        started = time.perf_counter()
        result = subprocess.run(command, cwd=repo_root, env=env)
        durations[gate_id] = time.perf_counter() - started
        if result.returncode != 0:
            raise SystemExit(f"Step '{label}' failed with exit code {result.returncode}")

    if args.no_aggregate:
        print("\n>>> Skipping aggregator step")
        return

    # Run the aggregator once to produce outputs, capturing its runtime.
    label, gate_id, command = AGGREGATOR_STEP
    print(f"\n>>> Running {label}")
    agg_started = time.perf_counter()
    agg_result = subprocess.run(command, cwd=repo_root, env=env)
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

    timings_path_env = env.get("PIPELINE_TIMINGS_PATH")
    timings_path = Path(timings_path_env) if timings_path_env else repo_root / "reports" / "timings.json"
    timings_path.parent.mkdir(parents=True, exist_ok=True)
    with timings_path.open("w", encoding="utf-8") as f:
        json.dump(timings_payload, f, indent=2)

    # Re-run the aggregator so it can ingest the timings.json payload for the
    # dashboard and consolidated summary files.
    print("\n>>> Refreshing Aggregator with timings")
    refresh_result = subprocess.run(command, cwd=repo_root, env=env)
    if refresh_result.returncode != 0:
        raise SystemExit(
            f"Refresh step '{label}' failed with exit code {refresh_result.returncode}"
        )

    print("\nPipeline completed. Aggregated report written to REPORT_SUMMARY.json")
    print("Timings written to", timings_path)


if __name__ == "__main__":
    main()
