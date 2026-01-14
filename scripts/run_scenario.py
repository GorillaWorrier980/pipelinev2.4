import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from devaisecops.config import get_config
from scenarios.definitions import (
    apply_data_quality_degradation,
    apply_explainability_shift,
    apply_pii_injection,
    apply_robustness_drop,
)


SCENARIOS = {
    "baseline",
    "data_quality_degradation",
    "pii_injection",
    "explainability_shift",
    "robustness_drop",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a scenario-based pipeline execution.")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=sorted(SCENARIOS),
        help="Scenario name to execute.",
    )
    parser.add_argument(
        "--config",
        default="configs/pipeline.config.json",
        help="Path to the pipeline config file.",
    )
    parser.add_argument(
        "--gates",
        default=None,
        help="Comma-separated gate list to override enabled_gates.",
    )
    return parser.parse_args()


def copy_inputs(run_inputs: Path) -> None:
    source = REPO_ROOT / "artifacts"
    shutil.copytree(source, run_inputs / "artifacts")
    config_source = REPO_ROOT / "configs" / "art"
    if config_source.exists():
        shutil.copytree(config_source, run_inputs / "configs" / "art")


def main() -> None:
    args = parse_args()
    scenario = args.scenario
    pipeline_config = get_config(args.config)
    scenario_settings = pipeline_config.get("scenarios", {})
    run_mode = pipeline_config.get("run_mode", "unknown")

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = REPO_ROOT / "runs" / timestamp / scenario
    run_inputs = run_dir / "inputs"
    run_outputs = run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    run_inputs.mkdir(parents=True, exist_ok=True)
    run_outputs.mkdir(parents=True, exist_ok=True)

    copy_inputs(run_inputs)

    metadata = {
        "scenario": scenario,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "run_mode": run_mode,
        "inputs_root": str(run_inputs),
        "outputs_root": str(run_outputs),
        "expected_failed_gates": [],
        "parameters": {},
        "gates_override": args.gates,
    }

    shap_weights_override = None
    art_weights_override = None
    art_config_override = run_inputs / "configs" / "art" / "config.json"

    if scenario == "data_quality_degradation":
        ratio = float(scenario_settings.get("data_quality_degradation", {}).get("row_ratio", 0.34))
        metadata["parameters"] = apply_data_quality_degradation(run_inputs, ratio)
        metadata["expected_failed_gates"] = ["ge"]
    elif scenario == "pii_injection":
        ratio = float(scenario_settings.get("pii_injection", {}).get("row_ratio", 0.34))
        metadata["parameters"] = apply_pii_injection(run_inputs, ratio)
        metadata["expected_failed_gates"] = ["presidio"]
    elif scenario == "explainability_shift":
        metadata["parameters"] = apply_explainability_shift(run_inputs)
        shap_weights_override = Path(metadata["parameters"]["weights_path"])
        metadata["expected_failed_gates"] = ["shap"]
    elif scenario == "robustness_drop":
        metadata["parameters"] = apply_robustness_drop(run_inputs)
        art_weights_override = Path(metadata["parameters"]["weights_path"])
        metadata["expected_failed_gates"] = ["art"]
    else:
        metadata["parameters"] = {"mode": "baseline"}

    env = os.environ.copy()
    env.update(
        {
            "PIPELINE_CONFIG": args.config,
            "GE_INPUT": str(run_inputs / "artifacts" / "data" / "tabular" / "tabular_enron.csv"),
            "PRESIDIO_INPUT": str(run_inputs / "artifacts" / "data" / "text" / "enron_text.jsonl"),
            "SHAP_METADATA": str(run_inputs / "artifacts" / "models" / "classifier" / "metadata.json"),
            "SHAP_WEIGHTS": str(
                shap_weights_override
                if shap_weights_override
                else run_inputs / "artifacts" / "models" / "classifier" / "mnist_cnn_weights.json"
            ),
            "SHAP_REFERENCE": str(run_inputs / "artifacts" / "data" / "models" / "mnist_samples.json"),
            "ART_METADATA": str(run_inputs / "artifacts" / "models" / "classifier" / "metadata.json"),
            "ART_WEIGHTS": str(
                art_weights_override
                if art_weights_override
                else run_inputs / "artifacts" / "models" / "classifier" / "mnist_cnn_weights.json"
            ),
            "ART_REFERENCE": str(run_inputs / "artifacts" / "data" / "models" / "mnist_samples.json"),
            "ART_CONFIG": str(art_config_override),
            "RAGAS_CHUNKS": str(run_inputs / "artifacts" / "data" / "rag_chunks" / "chunks.jsonl"),
            "RAGAS_QA": str(run_inputs / "artifacts" / "data" / "qa" / "qa_set.jsonl"),
        }
    )

    env.update(
        {
            "GE_OUTPUT": str(run_outputs / "reports" / "ge" / "summary.json"),
            "PRESIDIO_OUTPUT": str(run_outputs / "reports" / "presidio" / "redaction_summary.json"),
            "SHAP_OUTPUT": str(run_outputs / "reports" / "shap" / "global.json"),
            "ART_OUTPUT": str(run_outputs / "reports" / "art" / "robustness.json"),
            "RAGAS_DETAIL": str(run_outputs / "reports" / "ragas" / "per_question.jsonl"),
            "RAGAS_SUMMARY": str(run_outputs / "reports" / "ragas" / "summary.json"),
            "AGGREGATOR_OUTPUT": str(run_outputs / "REPORT_SUMMARY.json"),
            "DASHBOARD_OUTPUT": str(run_outputs / "reports" / "dashboard" / "index.html"),
            "DASHBOARD_GATES_DIR": str(run_outputs / "reports" / "dashboard" / "gates"),
        }
    )

    timings_path = run_outputs / "reports" / "timings.json"
    env["PIPELINE_TIMINGS_PATH"] = str(timings_path)
    env["AGGREGATOR_TIMINGS"] = str(timings_path)

    metadata_path = run_dir / "scenario_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    command = [sys.executable, "scripts/run_pipeline.py", "--config", args.config]
    if args.gates:
        command.extend(["--gates", args.gates])
    result = subprocess.run(command, cwd=REPO_ROOT, env=env)
    if result.returncode != 0:
        raise SystemExit(f"Scenario run failed with exit code {result.returncode}")

    print("Scenario completed. Outputs written to", run_outputs)
    print("Scenario metadata written to", metadata_path)


if __name__ == "__main__":
    main()
