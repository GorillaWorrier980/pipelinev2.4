#!/bin/sh
set -euo pipefail
CONFIG_PATH="${TRIVY_CONFIG:-/configs/config.json}"
OUTPUT_PATH="${TRIVY_OUTPUT:-/reports/cve.json}"
SEVERITIES="${TRIVY_SEVERITY:-CRITICAL,HIGH}"
FORMAT="${TRIVY_FORMAT:-json}"
IMAGE=$(jq -r '.image' "${CONFIG_PATH}")
exec trivy image --format "${FORMAT}" --output "${OUTPUT_PATH}" --severity "${SEVERITIES}" "${IMAGE}"
