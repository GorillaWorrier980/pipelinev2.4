import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import shap


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


def main():
    model_path = Path(os.environ.get("SHAP_MODEL", "artifacts/models/classifier/mnist_cnn.pt"))
    metadata_path = Path(os.environ.get("SHAP_METADATA", "artifacts/models/classifier/metadata.json"))
    output_path = Path(os.environ.get("SHAP_OUTPUT", "reports/shap/global.json"))

    metadata = load_metadata(metadata_path)
    input_shape = tuple(metadata.get("input_shape", [1, 28, 28]))
    num_classes = int(metadata.get("num_classes", 10))
    sample_override = os.environ.get("SHAP_SAMPLE_DATA")
    if sample_override:
        sample_path = Path(sample_override)
    else:
        sample_path = Path(metadata.get("sample_data", "artifacts/data/models/mnist_samples.npz"))

    images, labels = ensure_samples(sample_path, input_shape)
    model = load_model(model_path, num_classes)

    background = torch.tensor(images[:5]).float()
    test_images = torch.tensor(images[5:]).float()

    explainer = shap.DeepExplainer(model, background)
    shap_values = explainer.shap_values(test_images)

    os.makedirs(output_path.parent, exist_ok=True)
    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "input_model": str(model_path),
        "metadata": metadata,
        "sample_size": int(test_images.shape[0]),
        "mean_abs_shap": [float(np.mean(np.abs(values))) for values in shap_values],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
