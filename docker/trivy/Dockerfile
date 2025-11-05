FROM aquasec/trivy:0.45.0
RUN apk add --no-cache jq
COPY run_trivy.sh /run_trivy.sh
RUN chmod +x /run_trivy.sh
ENV TRIVY_CONFIG=/configs/config.json \
    TRIVY_OUTPUT=/reports/cve.json \
    TRIVY_SEVERITY=CRITICAL,HIGH \
    TRIVY_FORMAT=json
ENTRYPOINT ["/run_trivy.sh"]
