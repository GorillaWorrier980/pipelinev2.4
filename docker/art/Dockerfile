FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY run_art.py ./

ENV ART_MODEL=/artifacts/mnist_cnn.pt \
    ART_METADATA=/artifacts/metadata.json \
    ART_CONFIG=/configs/config.json \
    ART_OUTPUT=/reports/robustness.json

ENTRYPOINT ["python", "run_art.py"]
