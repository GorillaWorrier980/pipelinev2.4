FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY run_expectations.py ./

ENV GE_INPUT=/data/tabular_enron.csv \
    GE_OUTPUT=/reports/summary.json

ENTRYPOINT ["python", "run_expectations.py"]
