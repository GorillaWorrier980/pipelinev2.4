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
}

DEFAULT_CONFIG: Dict[str, object] = {
    "epsilon": 0.1,
    "epsilon_step": 0.04,
    "max_iter": 5,
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


def load_config(path: Optional[Path]) -> Tuple[Dict[str, object], Optional[Path]]:
    config = DEFAULT_CONFIG.copy()
    source: Optional[Path] = None
    if path:
        payload = load_json(path)
        if payload:
            config.update(payload)
            source = path
    return config, source


def load_weights(path: Path) -> Tuple[List[List[float]], List[float], Optional[Path]]:
    payload = load_json(path)
    if payload and isinstance(payload.get("weights"), list):
        weights = payload["weights"]
        bias = payload.get("bias")
        if not isinstance(bias, list):
            bias = [0.0] * len(weights)
        return weights, bias, path
    return [[1.0]], [0.0], None


def load_samples(path: Path) -> Tuple[List[List[float]], List[int], Optional[Path]]:
    payload = load_json(path)
    if payload:
        inputs = payload.get("inputs")
        labels = payload.get("labels")
        if isinstance(inputs, list) and isinstance(labels, list) and len(inputs) == len(labels):
            return inputs, labels, path
    return [[0.0]], [0], None


def softmax(logits: Sequence[float]) -> List[float]:
    maximum = max(logits)
    exps = [math.exp(value - maximum) for value in logits]
    total = sum(exps) or 1.0
    return [value / total for value in exps]


def logits_for_sample(weights: Sequence[Sequence[float]], bias: Sequence[float], sample: Sequence[float]) -> List[float]:
    return [
        sum(weight * feature for weight, feature in zip(class_weights, sample)) + bias[idx]
        for idx, class_weights in enumerate(weights)
    ]


def predict(weights: Sequence[Sequence[float]], bias: Sequence[float], sample: Sequence[float]) -> Tuple[int, List[float]]:
    logits = logits_for_sample(weights, bias, sample)
    probabilities = softmax(logits)
    return max(range(len(probabilities)), key=lambda index: probabilities[index]), probabilities


def accuracy(
    weights: Sequence[Sequence[float]],
    bias: Sequence[float],
    samples: Sequence[Sequence[float]],
    labels: Sequence[int],
) -> float:
    correct = 0
    for sample, label in zip(samples, labels):
        prediction, _ = predict(weights, bias, sample)
        if prediction == label:
            correct += 1
    return correct / len(samples) if samples else 0.0


def gradient(
    weights: Sequence[Sequence[float]],
    bias: Sequence[float],
    sample: Sequence[float],
    label: int,
) -> List[float]:
    logits = logits_for_sample(weights, bias, sample)
    probabilities = softmax(logits)
    grad = [0.0] * len(sample)
    for class_idx, class_weights in enumerate(weights):
        coefficient = probabilities[class_idx] - (1.0 if class_idx == label else 0.0)
        for feature_idx, weight in enumerate(class_weights):
            grad[feature_idx] += coefficient * weight
    return grad


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def apply_fgsm(sample: Sequence[float], label: int, weights, bias, epsilon: float) -> List[float]:
    grad = gradient(weights, bias, sample, label)
    perturbed = []
    for feature, grad_value in zip(sample, grad):
        perturbed.append(clamp(feature + epsilon * sign(grad_value), 0.0, 1.0))
    return perturbed


def apply_pgd(sample: Sequence[float], label: int, weights, bias, epsilon: float, epsilon_step: float, max_iter: int) -> List[float]:
    original = list(sample)
    adversarial = list(sample)
    for _ in range(max_iter):
        grad = gradient(weights, bias, adversarial, label)
        adversarial = [feature + epsilon_step * sign(grad_value) for feature, grad_value in zip(adversarial, grad)]
        adversarial = [clamp(value, orig - epsilon, orig + epsilon) for value, orig in zip(adversarial, original)]
        adversarial = [clamp(value, 0.0, 1.0) for value in adversarial]
    return adversarial


def evaluate_attack(samples, labels, generator):
    generated = [generator(sample, label) for sample, label in zip(samples, labels)]
    return generated


def main() -> None:
    base_dir = Path("artifacts")
    metadata_env = os.environ.get("ART_METADATA")
    weights_env = os.environ.get("ART_WEIGHTS")
    data_env = os.environ.get("ART_REFERENCE")
    config_env = os.environ.get("ART_CONFIG")

    metadata_path = Path(metadata_env) if metadata_env else base_dir / "models/classifier/metadata.json"
    weights_path = Path(weights_env) if weights_env else base_dir / "models/classifier/mnist_cnn_weights.json"
    samples_path = Path(data_env) if data_env else base_dir / "data/models/mnist_samples.json"
    config_path = Path(config_env) if config_env else Path("configs/art/config.json")
    output_path = Path(os.environ.get("ART_OUTPUT", "reports/art/robustness.json"))

    metadata, metadata_source = load_metadata(metadata_path)
    config, config_source = load_config(config_path)
    weights, bias, weights_source = load_weights(weights_path)
    samples, labels, samples_source = load_samples(samples_path)

    epsilon = float(config.get("epsilon", DEFAULT_CONFIG["epsilon"]))
    epsilon_step = float(config.get("epsilon_step", DEFAULT_CONFIG["epsilon_step"]))
    max_iter = int(config.get("max_iter", DEFAULT_CONFIG["max_iter"]))

    clean_acc = accuracy(weights, bias, samples, labels)

    fgsm_samples = evaluate_attack(
        samples,
        labels,
        lambda sample, label: apply_fgsm(sample, label, weights, bias, epsilon),
    )
    fgsm_acc = accuracy(weights, bias, fgsm_samples, labels)

    pgd_samples = evaluate_attack(
        samples,
        labels,
        lambda sample, label: apply_pgd(sample, label, weights, bias, epsilon, epsilon_step, max_iter),
    )
    pgd_acc = accuracy(weights, bias, pgd_samples, labels)

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "metadata": metadata,
        "metadata_source": str(metadata_source) if metadata_source else "defaults",
        "weights_source": str(weights_source) if weights_source else "defaults",
        "reference_source": str(samples_source) if samples_source else "defaults",
        "config": config,
        "config_source": str(config_source) if config_source else "defaults",
        "clean_accuracy": round(clean_acc, 4),
        "attacks": {
            "fgsm": {
                "adv_accuracy": round(fgsm_acc, 4),
                "accuracy_drop": round(max(clean_acc - fgsm_acc, 0.0), 4),
            },
            "pgd": {
                "adv_accuracy": round(pgd_acc, 4),
                "accuracy_drop": round(max(clean_acc - pgd_acc, 0.0), 4),
            },
        },
    }

    os.makedirs(output_path.parent, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)


if __name__ == "__main__":
    main()
