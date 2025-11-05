FROM python:3.10-slim

WORKDIR /app
COPY run_aggregator.py ./

ENV AGGREGATOR_OUTPUT=/reports/REPORT_SUMMARY.json

ENTRYPOINT ["python", "run_aggregator.py"]
