FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY run_shap.py ./

ENV SHAP_MODEL=/artifacts/mnist_cnn.pt \
    SHAP_OUTPUT=/reports/global.json

ENTRYPOINT ["python", "run_shap.py"]
