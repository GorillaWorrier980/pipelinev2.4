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
    models/                          # Generated automatically if absent
  models/
    classifier/
      metadata.json                  # Model metadata consumed by SHAP/ART
      mnist_cnn.pt                   # Placeholder weights (auto-generated if empty)
    vector_index/index.faiss         # Placeholder FAISS index
configs/
  art/config.json                    # ART attack settings
  trivy/config.json                  # Target image for Trivy
reports/
  ...                                # JSON outputs written by each gate
```

## Usage

1. Populate the `artifacts/` folders with your data, model, and index assets. The repository ships with lightweight samples so the pipeline can run end-to-end without external downloads.
2. (Optional) Adjust configuration files under `configs/`.
3. Run the full pipeline locally (no Docker required) using the lightweight Python entrypoints:

   ```bash
   python run_pipeline.py
   ```

   Each gate is executed sequentially and the aggregated report is refreshed at the end of the run.

4. (Optional) You can still orchestrate the original Docker services via `docker compose up --build` if you prefer container isolation.

5. When the run completes, inspect the individual reports under `reports/**` and the consolidated `REPORT_SUMMARY.json` at the repository root.

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
* `REPORT_SUMMARY.json` – Aggregated snapshot across all gates

## Extending

* Update expectation logic in `docker/ge/run_expectations.py` for domain-specific validations.
* Customize Presidio recognizers or anonymizers inside `docker/presidio/run_presidio.py`.
* Swap in a trained model by replacing `artifacts/models/classifier/mnist_cnn.pt` and updating `metadata.json`.
* Provide a real FAISS index and larger QA/chunk datasets to align with your RAG deployment.

## License

This repository is provided as-is for demonstration and can be adapted to suit internal pipelines.
