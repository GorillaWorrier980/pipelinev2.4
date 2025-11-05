import json
import hashlib
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Dict


def load_config(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    config_path = Path(os.environ.get("TRIVY_CONFIG", "configs/trivy/config.json"))
    output_path = Path(os.environ.get("TRIVY_OUTPUT", "reports/trivy/cve.json"))

    config = load_config(config_path)
    image = config.get("image", "unknown:image")

    digest = hashlib.sha256(image.encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:8], 16))

    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    findings = []
    severity_summary = {}
    for severity in severities:
        count = rng.randint(0, 3)
        severity_summary[severity] = count
        for idx in range(count):
            findings.append(
                {
                    "id": f"{severity}-SIM-{idx+1}",
                    "severity": severity,
                    "package": rng.choice(["openssl", "glibc", "python", "libssl"]),
                    "title": f"Simulated {severity.lower()} vulnerability",
                }
            )

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "image": image,
        "severity_summary": severity_summary,
        "findings": findings,
    }

    os.makedirs(output_path.parent, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)


if __name__ == "__main__":
    main()
