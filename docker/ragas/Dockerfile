FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY run_ragas.py ./

ENV RAGAS_CHUNKS=/data/chunks.jsonl \
    RAGAS_QA=/data/qa_set.jsonl \
    RAGAS_DETAIL=/reports/per_question.jsonl \
    RAGAS_SUMMARY=/reports/summary.json

ENTRYPOINT ["python", "run_ragas.py"]
