# Pipeline v2.4 Toolchain

This repository packages five independent quality gates – data validation, PII scanning, model explainability, adversarial robustness, and retrieval evaluation – plus a final report aggregator. Every gate runs inside its own Docker container and consumes artifacts from the `artifacts/` folder while producing JSON reports under `reports/`.

## Prerequisites

* Docker and Docker Compose v2

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
  art/config.json                    # FGSM/PGD parameters for the ART gate
reports/
  ...                                # JSON outputs written by each gate
```

## Usage

1. Populate the `artifacts/` folders with your data, model, and index assets. The repository ships with lightweight samples so the pipeline can run end-to-end without external downloads.
2. Run the full pipeline locally (no Docker required) using the lightweight Python entrypoints:

   ```bash
   python run_pipeline.py
   ```

   Each gate is executed sequentially and the aggregated report is refreshed at the end of the run.

3. (Optional) You can still orchestrate the original Docker services via `docker compose up --build` if you prefer container isolation.

4. When the run completes, inspect the individual reports under `reports/**`, the consolidated `REPORT_SUMMARY.json` at the repository root, and the HTML dashboard at `reports/dashboard/index.html` for a quick pass/fail snapshot.

### SHAP & ART Defaults

The SHAP and ART gates evaluate a bundled MNIST-style linear classifier using real weights and a small reference set stored under `artifacts/models/classifier/mnist_cnn_weights.json` and `artifacts/data/models/mnist_samples.json`. The explainability step computes mean absolute SHAP contributions from those samples, while the robustness gate launches FGSM and PGD perturbations against the same model. Override the inputs and optional metadata/configuration via the `SHAP_*` and `ART_*` environment variables when supplying your own model artifacts.

### Gate data coverage and transformations

Each gate consumes a well-defined slice of the sample artifacts so you can trace exactly which inputs power every report:

| Gate | Primary inputs | How the data is used |
| --- | --- | --- |
| Great Expectations | `artifacts/data/tabular/tabular_enron.csv` | Loads all columns from the CSV (message metadata) to validate non-null constraints, enforce ISO timestamp formatting for `sent_at`, verify `message_id` uniqueness, and restrict `has_attachment` to `true/false`. |
| Presidio | `artifacts/data/text/enron_text.jsonl` | Reads every JSONL row, concatenates the `subject` and `body` fields into a single string per message, detects EMAIL/PHONE/NAME entities with regex recognizers, and emits anonymized samples for any hits. |
| SHAP | `artifacts/models/classifier/metadata.json`, `artifacts/models/classifier/mnist_cnn_weights.json`, `artifacts/data/models/mnist_samples.json` | Loads the classifier metadata to capture model context, ingests the linear weights/biases, and processes all reference feature vectors to compute baseline-adjusted, probability-weighted mean absolute SHAP importances. |
| ART | `artifacts/models/classifier/metadata.json`, `artifacts/models/classifier/mnist_cnn_weights.json`, `artifacts/data/models/mnist_samples.json`, `configs/art/config.json` | Uses the same model artifacts plus FGSM/PGD settings to score clean accuracy over the reference samples, generate adversarial perturbations per the config, and measure accuracy drops under each attack. |
| RAGAS | `artifacts/data/rag_chunks/chunks.jsonl`, `artifacts/data/qa/qa_set.jsonl` | Loads all knowledge chunks and QA pairs, aligns each question with its referenced chunk IDs, checks whether gold answers appear in the retrieved context text, and aggregates per-question support metrics into a global summary. |

### Configuration reference

The gates are lightweight Python scripts that honor environment variables so you can redirect inputs, tweak parameters, and change report locations without editing code. The following table lists the relevant settings and their defaults:

| Gate | Environment variables | Default | Purpose |
| --- | --- | --- | --- |
| Great Expectations | `GE_INPUT` | `artifacts/data/tabular/tabular_enron.csv` | Path to the CSV file that will be validated. |
|  | `GE_OUTPUT` | `reports/ge/summary.json` | Where the expectation summary is written. |
| Presidio | `PRESIDIO_INPUT` | `artifacts/data/text/enron_text.jsonl` | JSONL source of emails to scan (subject + body). |
|  | `PRESIDIO_OUTPUT` | `reports/presidio/redaction_summary.json` | Destination for the entity counts and anonymized examples. |
| SHAP | `SHAP_METADATA` | `artifacts/models/classifier/metadata.json` | Optional override describing the model (name, architecture, class count). |
|  | `SHAP_WEIGHTS` | `artifacts/models/classifier/mnist_cnn_weights.json` | Linear weights/biases consumed when computing importance scores. |
|  | `SHAP_REFERENCE` | `artifacts/data/models/mnist_samples.json` | Reference feature vectors and labels that anchor SHAP calculations. |
|  | `SHAP_OUTPUT` | `reports/shap/global.json` | Location for the global mean absolute SHAP report. |
| ART | `ART_METADATA` | `artifacts/models/classifier/metadata.json` | Model description used in the robustness report metadata. |
|  | `ART_WEIGHTS` | `artifacts/models/classifier/mnist_cnn_weights.json` | Weights and biases for the classifier under attack. |
|  | `ART_REFERENCE` | `artifacts/data/models/mnist_samples.json` | Clean evaluation samples that attacks are generated from. |
|  | `ART_CONFIG` | `configs/art/config.json` | JSON payload defining FGSM/PGD parameters (`epsilon`, `epsilon_step`, `max_iter`). |
|  | `ART_OUTPUT` | `reports/art/robustness.json` | Path for the robustness summary (clean/adv accuracy + drops). |
| RAGAS | `RAGAS_CHUNKS` | `artifacts/data/rag_chunks/chunks.jsonl` | Knowledge base fragments referenced by QA items. |
|  | `RAGAS_QA` | `artifacts/data/qa/qa_set.jsonl` | Question/answer pairs with chunk identifiers. |
|  | `RAGAS_DETAIL` | `reports/ragas/per_question.jsonl` | Detailed per-question support output. |
|  | `RAGAS_SUMMARY` | `reports/ragas/summary.json` | Aggregate retrieval support statistics. |
| Aggregator | `REPORT_GE`, `REPORT_PRESIDIO`, `REPORT_SHAP`, `REPORT_ART`, `REPORT_RAGAS` | defaults to corresponding `reports/**` paths | Allows pointing the aggregator at custom report locations if they were generated elsewhere. |
|  | `AGGREGATOR_OUTPUT` | `REPORT_SUMMARY.json` | Where the consolidated JSON snapshot is written. |
|  | `DASHBOARD_OUTPUT` | `reports/dashboard/index.html` | Destination for the HTML pass/fail dashboard. |
|  | `DASHBOARD_GATES_DIR` | `reports/dashboard/gates` | Folder that receives per-gate status JSON summaries. |

All environment variables can be set when calling `python run_pipeline.py` (e.g. `GE_INPUT=/tmp/data.csv python run_pipeline.py`) or passed through `docker compose` via the corresponding service definitions.

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
* `reports/dashboard/gates/*.json` – Pass/fail snapshots for each gate (mirrors dashboard rows)
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

### RAGAS scoring without an external LLM

The bundled RAGAS script keeps the evaluation entirely offline. Instead of calling a hosted "LLM as a Judge" endpoint, it
computes lexical support scores by checking whether each gold answer string appears in the retrieved context snippets. This
deterministic heuristic mimics the spirit of a grounding check without network calls, which makes the demo safe to run in CI
or air-gapped environments. Supplying a custom RAGAS configuration or model-backed judge is still possible—override the entry
point with your own implementation if you need true LLM-based scoring.

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
