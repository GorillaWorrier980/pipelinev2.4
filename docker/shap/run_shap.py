import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


DEFAULT_METADATA: Dict[str, object] = {
    "name": "mnist_demo",
    "dataset": "mnist",
    "architecture": "linear_mnist_demo",
    "num_classes": 10,
    "input_shape": [1, 4, 4],
}


def load_json(path: Path) -> Optional[Dict[str, object]]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(payload, dict):
        return payload
    return None


def load_metadata(path: Optional[Path]) -> Tuple[Dict[str, object], Optional[Path]]:
    metadata = DEFAULT_METADATA.copy()
    source: Optional[Path] = None
    if path:
        payload = load_json(path)
        if payload:
            metadata.update(payload)
            source = path
    return metadata, source


def load_weights(path: Path) -> Tuple[List[List[float]], List[float], Optional[Path]]:
    payload = load_json(path)
    if payload and isinstance(payload.get("weights"), list):
        weights = payload["weights"]
        bias = payload.get("bias")
        if not isinstance(bias, list):
            bias = [0.0] * len(weights)
        return weights, bias, path
    # fall back to tiny identity weights so downstream steps do not crash
    weights = [[1.0]]
    bias = [0.0]
    return weights, bias, None


def load_reference_inputs(path: Path) -> Tuple[List[List[float]], List[int], Optional[Path]]:
    payload = load_json(path)
    if payload:
        inputs = payload.get("inputs")
        labels = payload.get("labels")
        if isinstance(inputs, list) and isinstance(labels, list) and len(inputs) == len(labels):
            return inputs, labels, path
    # Provide a fallback single-sample dataset
    return [[0.0]], [0], None


def softmax(logits: Sequence[float]) -> List[float]:
    maximum = max(logits)
    exps = [math.exp(value - maximum) for value in logits]
    total = sum(exps) or 1.0
    return [value / total for value in exps]


def baseline_vector(samples: Sequence[Sequence[float]]) -> List[float]:
    if not samples:
        return [0.0]
    feature_count = len(samples[0])
    sums = [0.0] * feature_count
    for sample in samples:
        for idx, value in enumerate(sample):
            sums[idx] += value
    return [total / len(samples) for total in sums]


def compute_logits(weights: Sequence[Sequence[float]], bias: Sequence[float], sample: Sequence[float]) -> List[float]:
    logits = []
    for class_idx, class_weights in enumerate(weights):
        total = sum(weight * feature for weight, feature in zip(class_weights, sample))
        total += bias[class_idx]
        logits.append(total)
    return logits


def mean_abs_importance(
    weights: Sequence[Sequence[float]],
    bias: Sequence[float],
    samples: Sequence[Sequence[float]],
) -> List[float]:
    if not samples:
        return [1.0]
    baseline = baseline_vector(samples)
    totals = [0.0 for _ in weights]
    for sample in samples:
        logits = compute_logits(weights, bias, sample)
        probabilities = softmax(logits)
        for class_idx, class_weights in enumerate(weights):
            contributions = 0.0
            for feature_idx, weight in enumerate(class_weights):
                delta = sample[feature_idx] - baseline[feature_idx]
                contributions += abs(delta * weight)
            totals[class_idx] += probabilities[class_idx] * contributions
    grand_total = sum(totals) or 1.0
    return [round(total / grand_total, 4) for total in totals]


def main() -> None:
    base_dir = Path("artifacts")
    metadata_env = os.environ.get("SHAP_METADATA")
    weights_env = os.environ.get("SHAP_WEIGHTS")
    reference_env = os.environ.get("SHAP_REFERENCE")

    metadata_path = Path(metadata_env) if metadata_env else base_dir / "models/classifier/metadata.json"
    weights_path = Path(weights_env) if weights_env else base_dir / "models/classifier/mnist_cnn_weights.json"
    reference_path = Path(reference_env) if reference_env else base_dir / "data/models/mnist_samples.json"
    output_path = Path(os.environ.get("SHAP_OUTPUT", "reports/shap/global.json"))

    metadata, metadata_source = load_metadata(metadata_path)
    weights, bias, weights_source = load_weights(weights_path)
    samples, labels, reference_source = load_reference_inputs(reference_path)

    importances = mean_abs_importance(weights, bias, samples)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "metadata": metadata,
        "metadata_source": str(metadata_source) if metadata_source else "defaults",
        "weights_source": str(weights_source) if weights_source else "defaults",
        "reference_source": str(reference_source) if reference_source else "defaults",
        "sample_size": len(samples),
        "label_distribution": {str(label): labels.count(label) for label in set(labels)},
        "mean_abs_shap": importances,
    }

    os.makedirs(output_path.parent, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


if __name__ == "__main__":
    main()
