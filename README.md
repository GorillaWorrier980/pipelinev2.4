# Pipeline v2.4 Toolchain

This repository packages six independent quality gates – data validation, PII scanning, model explainability, adversarial robustness, retrieval evaluation, and supply-chain scanning – plus a final report aggregator. Every gate runs inside its own Docker container and consumes artifacts from the `artifacts/` folder while producing JSON reports under `reports/`.

## Prerequisites

* Docker and Docker Compose v2
* (Optional) Internet access for pulling the OWASP Juice Shop image used by the Trivy scan

## Repository Layout

```
artifacts/
  data/
    tabular/tabular_enron.csv        # GE input sample
    text/enron_text.jsonl            # Presidio input sample
    rag_chunks/chunks.jsonl          # RAGAS knowledge base sample
    qa/qa_set.jsonl                  # RAGAS question/answer sample
    models/mnist_samples.json        # Reference inputs for SHAP/ART gates
  models/
    classifier/
      metadata.json                  # Model description shared by SHAP/ART
      mnist_cnn_weights.json         # Lightweight linear model weights
    vector_index/index.faiss         # Placeholder FAISS index
configs/
  trivy/config.json                  # Target image for Trivy
reports/
  ...                                # JSON outputs written by each gate
```

## Usage

1. Populate the `artifacts/` folders with your data, model, and index assets. The repository ships with lightweight samples so the pipeline can run end-to-end without external downloads.
2. (Optional) Adjust configuration files under `configs/` (only Trivy needs one by default).
3. Run the full pipeline locally (no Docker required) using the lightweight Python entrypoints:

   ```bash
   python run_pipeline.py
   ```

   Each gate is executed sequentially and the aggregated report is refreshed at the end of the run.

4. (Optional) You can still orchestrate the original Docker services via `docker compose up --build` if you prefer container isolation.

5. When the run completes, inspect the individual reports under `reports/**`, the consolidated `REPORT_SUMMARY.json` at the repository root, and the HTML dashboard at `reports/dashboard/index.html` for a quick pass/fail snapshot.

### SHAP & ART Defaults

The SHAP and ART gates now evaluate a bundled MNIST-style linear classifier using real weights and a small reference set stored under `artifacts/models/classifier/mnist_cnn_weights.json` and `artifacts/data/models/mnist_samples.json`. The explainability step computes mean absolute SHAP contributions from those samples, while the robustness gate launches FGSM and PGD perturbations against the same model. Override the inputs and optional metadata/configuration via the `SHAP_*` and `ART_*` environment variables when supplying your own model artifacts.

### Individual Containers

Each service can be run independently. Example for Great Expectations:

```bash
docker compose run --build ge
```

All containers accept environment variables (see `docker-compose.yml`) so you can override input and output locations without editing the images.

## Outputs

* `reports/ge/summary.json` – Great Expectations validation statistics
* `reports/presidio/redaction_summary.json` – Presidio entity counts and examples
* `reports/shap/global.json` – Mean absolute SHAP contributions
* `reports/art/robustness.json` – Clean vs. adversarial accuracies
* `reports/ragas/*.json[l]` – Retrieval support metrics per question and summary
* `reports/trivy/cve.json` – Vulnerability report for the configured container image
* `reports/dashboard/index.html` – Human-friendly overview of gate status and pass criteria
* `REPORT_SUMMARY.json` – Aggregated snapshot across all gates, including structured pass/fail metadata

### Dashboard Pass Criteria

The dashboard summarizes each gate using the following success checks:

| Gate | Pass Criteria |
| --- | --- |
| Great Expectations | All configured expectations succeed. |
| Presidio | At least one PII entity is detected in the sample. |
| SHAP | Mean absolute importance scores sum to 1.0 (±0.01). |
| ART | FGSM and PGD adversarial accuracies remain ≥ 0.70. |
| RAGAS | Mean support score meets or exceeds 0.60. |
| Trivy | No HIGH or CRITICAL vulnerabilities found. |

## Continuous Integration

Every push and pull request triggers the **Run Quality Gates Pipeline** GitHub Action, which executes `python run_pipeline.py`
on Ubuntu and uploads the consolidated `REPORT_SUMMARY.json` as well as the HTML dashboard (`reports/dashboard/index.html`) as
build artifacts. Download the artifact from the workflow run page to review the structured JSON summary or open the dashboard
without executing the pipeline locally.

## Extending

* Update expectation logic in `docker/ge/run_expectations.py` for domain-specific validations.
* Customize Presidio recognizers or anonymizers inside `docker/presidio/run_presidio.py`.
* Swap in a trained model by updating the classifier metadata, weights, and sample set under `artifacts/models/classifier/` and `artifacts/data/models/`. The SHAP and ART gates assume a 10-class MNIST-style classifier by default, but you can override paths and settings via environment variables (see `docker/shap/run_shap.py` and `docker/art/run_art.py`).
* Provide a real FAISS index and larger QA/chunk datasets to align with your RAG deployment.

## License

This repository is provided as-is for demonstration and can be adapted to suit internal pipelines.
