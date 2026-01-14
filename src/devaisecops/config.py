from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


KNOWN_GATES = {"ge", "presidio", "shap", "art", "ragas"}

GATE_ALIASES = {
    "data_quality": "ge",
    "pii_scan": "presidio",
    "explainability": "shap",
    "robustness": "art",
    "rag_eval": "ragas",
    "sbom": "sbom",
}

DEFAULT_CONFIG: Dict[str, object] = {
    "run_mode": "full",
    "enabled_gates": ["data_quality", "pii_scan", "explainability", "robustness", "rag_eval"],
    "thresholds": {
        "ge": {"min_expectations": 1},
        "presidio": {"max_total_entities": 0},
        "shap": {"sum_target": 1.0, "tolerance": 0.01},
        "art": {"min_adv_accuracy": 0.7},
        "ragas": {"min_support": 0.6, "min_coverage": 0.6},
        "sbom": {"max_critical": 0, "max_high": 0},
    },
}


def _merge_dicts(base: Dict[str, object], override: Dict[str, object]) -> Dict[str, object]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path) -> Dict[str, object]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Pipeline config must be a JSON object.")
    return _merge_dicts(DEFAULT_CONFIG, payload)


def get_config(path: str | Path | None = None) -> Dict[str, object]:
    if path is None:
        return deepcopy(DEFAULT_CONFIG)
    return load_config(path)


def normalize_gate_names(gates: Iterable[str]) -> Tuple[List[str], List[str]]:
    resolved: List[str] = []
    unknown: List[str] = []
    for gate in gates:
        token = gate.strip().lower()
        if not token:
            continue
        mapped = GATE_ALIASES.get(token, token)
        if mapped in KNOWN_GATES:
            resolved.append(mapped)
        else:
            unknown.append(token)
    return resolved, unknown


def resolve_enabled_gates(
    config: Dict[str, object],
    override_gates: Iterable[str] | None = None,
) -> Tuple[List[str], List[str]]:
    if override_gates is not None:
        return normalize_gate_names(override_gates)
    configured = config.get("enabled_gates", [])
    if isinstance(configured, list):
        return normalize_gate_names(str(item) for item in configured)
    return [], []
