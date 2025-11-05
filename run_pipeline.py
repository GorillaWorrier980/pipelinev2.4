import subprocess
import sys
from pathlib import Path


STEPS = [
    ("Great Expectations", [sys.executable, "docker/ge/run_expectations.py"]),
    ("Presidio", [sys.executable, "docker/presidio/run_presidio.py"]),
    ("SHAP", [sys.executable, "docker/shap/run_shap.py"]),
    ("ART", [sys.executable, "docker/art/run_art.py"]),
    ("RAGAS", [sys.executable, "docker/ragas/run_ragas.py"]),
    ("Trivy", [sys.executable, "docker/trivy/run_trivy.py"]),
    ("Aggregator", [sys.executable, "docker/aggregator/run_aggregator.py"]),
]


def main() -> None:
    repo_root = Path(__file__).parent
    for label, command in STEPS:
        print(f"\n>>> Running {label}")
        result = subprocess.run(command, cwd=repo_root)
        if result.returncode != 0:
            raise SystemExit(f"Step '{label}' failed with exit code {result.returncode}")
    print("\nPipeline completed. Aggregated report written to REPORT_SUMMARY.json")


if __name__ == "__main__":
    main()
