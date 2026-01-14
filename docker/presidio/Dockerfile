FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt
COPY run_presidio.py ./

ENV PRESIDIO_INPUT=/data/enron_text.jsonl \
    PRESIDIO_OUTPUT=/reports/redaction_summary.json

ENTRYPOINT ["python", "run_presidio.py"]
