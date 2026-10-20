FROM openvino/ubuntu24_runtime:2026.2.0@sha256:9286c2999e7873b5ded0b76236331964a43c21c157d6b7f7dc7daa4166211bc1

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-venv ca-certificates curl gnupg && \
    curl -fsSLo /tmp/intel-graphics.key \
      https://repositories.intel.com/graphics/intel-graphics.key && \
    gpg --batch --dearmor -o /usr/share/keyrings/intel-graphics.gpg /tmp/intel-graphics.key && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/graphics/ubuntu noble main" \
      > /etc/apt/sources.list.d/intel-graphics.list && \
    apt-get update && apt-get install -y --no-install-recommends \
      intel-opencl-icd intel-level-zero-gpu level-zero clinfo && \
    rm -f /tmp/intel-graphics.key && \
    rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/bonsai-venv && \
    /opt/bonsai-venv/bin/python -m pip install --no-cache-dir \
    openvino==2026.2.0 openvino-genai==2026.2.0.0

COPY verify_bonsai.py server.py smoke.py /opt/bonsai/
WORKDIR /opt/bonsai
ENV PATH="/opt/bonsai-venv/bin:${PATH}"
ENV PYTHONPATH=""
ENTRYPOINT ["/opt/bonsai-venv/bin/python", "-u", "/opt/bonsai/server.py"]
