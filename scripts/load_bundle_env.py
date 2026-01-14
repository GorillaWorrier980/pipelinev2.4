import argparse
import json
from pathlib import Path


MANIFEST_KEYS = {
    "ge_input": "GE_INPUT",
    "presidio_input": "PRESIDIO_INPUT",
    "shap_metadata": "SHAP_METADATA",
    "shap_weights": "SHAP_WEIGHTS",
    "shap_reference": "SHAP_REFERENCE",
    "art_metadata": "ART_METADATA",
    "art_weights": "ART_WEIGHTS",
    "art_reference": "ART_REFERENCE",
    "ragas_chunks": "RAGAS_CHUNKS",
    "ragas_qa": "RAGAS_QA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load asset bundle manifest into env vars.")
    parser.add_argument(
        "--bundle-dir",
        required=True,
        help="Path to the unzipped asset bundle directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_dir = Path(args.bundle_dir)
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"manifest.json not found at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key, env_name in MANIFEST_KEYS.items():
        value = manifest.get(key)
        if value:
            print(f"{env_name}={bundle_dir}/{value}")


if __name__ == "__main__":
    main()
