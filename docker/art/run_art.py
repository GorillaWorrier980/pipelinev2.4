import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from art.attacks.evasion import FastGradientMethod, ProjectedGradientDescent
from art.estimators.classification import PyTorchClassifier


class SmallCNN(nn.Module):
    def __init__(self, num_classes: int = 10):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, 3, padding=1)
        self.conv2 = nn.Conv2d(8, 16, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.relu = nn.ReLU()
        self.fc1 = nn.Linear(16 * 7 * 7, 64)
        self.fc2 = nn.Linear(64, num_classes)

    def forward(self, x):
        x = self.relu(self.conv1(x))
        x = self.pool(x)
        x = self.relu(self.conv2(x))
        x = self.pool(x)
        x = torch.flatten(x, 1)
        x = self.relu(self.fc1(x))
        x = self.fc2(x)
        return x


def load_metadata(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_samples(sample_path: Path, input_shape):
    if sample_path.exists() and sample_path.stat().st_size > 0:
        data = np.load(sample_path)
        return data["images"], data["labels"]

    sample_path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    images = rng.random((10, *input_shape), dtype=np.float32)
    labels = rng.integers(0, 10, size=(10,), dtype=np.int64)
    np.savez(sample_path, images=images, labels=labels)
    return images, labels


def load_model(weight_path: Path, num_classes: int) -> nn.Module:
    model = SmallCNN(num_classes=num_classes)
    if weight_path.exists() and weight_path.stat().st_size > 0:
        state_dict = torch.load(weight_path, map_location="cpu")
        model.load_state_dict(state_dict)
    else:
        weight_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), weight_path)
    model.eval()
    return model


def evaluate_accuracy(model: nn.Module, images: np.ndarray, labels: np.ndarray) -> float:
    with torch.no_grad():
        inputs = torch.tensor(images).float()
        outputs = model(inputs)
        predictions = outputs.argmax(dim=1).cpu().numpy()
    return float((predictions == labels).mean())


def main():
    model_path = Path(os.environ.get("ART_MODEL", "artifacts/models/classifier/mnist_cnn.pt"))
    metadata_path = Path(os.environ.get("ART_METADATA", "artifacts/models/classifier/metadata.json"))
    config_path = Path(os.environ.get("ART_CONFIG", "configs/art/config.json"))
    output_path = Path(os.environ.get("ART_OUTPUT", "reports/art/robustness.json"))

    metadata = load_metadata(metadata_path)
    input_shape = tuple(metadata.get("input_shape", [1, 28, 28]))
    sample_override = os.environ.get("ART_SAMPLE_DATA")
    if sample_override:
        sample_path = Path(sample_override)
    else:
        sample_path = Path(metadata.get("sample_data", "artifacts/data/models/mnist_samples.npz"))
    num_classes = int(metadata.get("num_classes", 10))

    images, labels = ensure_samples(sample_path, input_shape)
    model = load_model(model_path, num_classes)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    classifier = PyTorchClassifier(
        model=model,
        loss=torch.nn.CrossEntropyLoss(),
        optimizer=torch.optim.Adam(model.parameters(), lr=0.001),
        input_shape=input_shape,
        nb_classes=num_classes,
        clip_values=(0.0, 1.0),
    )

    clean_acc = evaluate_accuracy(model, images, labels)

    fgsm = FastGradientMethod(estimator=classifier, eps=config.get("epsilon", 0.2))
    adv_images_fgsm = fgsm.generate(x=images)
    adv_acc_fgsm = evaluate_accuracy(model, adv_images_fgsm, labels)

    pgd = ProjectedGradientDescent(
        estimator=classifier,
        eps=config.get("epsilon", 0.2),
        eps_step=config.get("epsilon_step", 0.02),
        max_iter=config.get("max_iter", 10),
        norm=np.inf,
    )
    adv_images_pgd = pgd.generate(x=images)
    adv_acc_pgd = evaluate_accuracy(model, adv_images_pgd, labels)

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "input_model": str(model_path),
        "config": config,
        "clean_accuracy": clean_acc,
        "attacks": {
            "fgsm": {
                "adv_accuracy": adv_acc_fgsm,
                "accuracy_drop": clean_acc - adv_acc_fgsm,
            },
            "pgd": {
                "adv_accuracy": adv_acc_pgd,
                "accuracy_drop": clean_acc - adv_acc_pgd,
            },
        },
    }

    os.makedirs(output_path.parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
