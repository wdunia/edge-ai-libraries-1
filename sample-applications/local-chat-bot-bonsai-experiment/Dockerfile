FROM openvino/ubuntu24_runtime:2026.2.0@sha256:9286c2999e7873b5ded0b76236331964a43c21c157d6b7f7dc7daa4166211bc1

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-venv ca-certificates curl libze1 ocl-icd-libopencl1 clinfo && \
    mkdir -p /tmp/intel-gpu && cd /tmp/intel-gpu && \
    curl -fL --retry 3 -O https://github.com/intel/intel-graphics-compiler/releases/download/v2.38.2/intel-igc-core-2_2.38.2+22051_amd64.deb && \
    curl -fL --retry 3 -O https://github.com/intel/intel-graphics-compiler/releases/download/v2.38.2/intel-igc-opencl-2_2.38.2+22051_amd64.deb && \
    curl -fL --retry 3 -O https://github.com/intel/compute-runtime/releases/download/26.27.39122.11/libigdgmm12_22.10.0_amd64.deb && \
    curl -fL --retry 3 -O https://github.com/intel/compute-runtime/releases/download/26.27.39122.11/intel-ocloc_26.27.39122.11-0_amd64.deb && \
    curl -fL --retry 3 -O https://github.com/intel/compute-runtime/releases/download/26.27.39122.11/intel-opencl-icd_26.27.39122.11-0_amd64.deb && \
    curl -fL --retry 3 -O https://github.com/intel/compute-runtime/releases/download/26.27.39122.11/libze-intel-gpu1_26.27.39122.11-0_amd64.deb && \
    printf '%s\n' \
      '3dbcbe4e716d62e9bd43a4a476d724cf772b4581dbcdd096d70df382e7ccad7e  intel-igc-core-2_2.38.2+22051_amd64.deb' \
      'e265d191590efd5491bfbbd148c144fdd40aea51e0b57f8651130d2da20b8186  intel-igc-opencl-2_2.38.2+22051_amd64.deb' \
      '6031a63d6e8a12ce61c14efc15f2c8e727061286e3820b8594e6d00615e04d54  libigdgmm12_22.10.0_amd64.deb' \
      '794a77217b3fd4c3f1381c2bb2c3c11a7f81e338b55b8a11e6c3b5070d138f98  intel-ocloc_26.27.39122.11-0_amd64.deb' \
      '6e447a783c99fb5634df298c135a81165be07db98672df96cdf413d22f3e6ac4  intel-opencl-icd_26.27.39122.11-0_amd64.deb' \
      '58420df60d4bf8ac79aba03f7de1b8b60a93e995b18142391077ff735ce7b74b  libze-intel-gpu1_26.27.39122.11-0_amd64.deb' \
      | sha256sum -c - && \
    apt-get install -y --no-install-recommends ./*.deb && \
    rm -rf /tmp/intel-gpu && \
    rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/bonsai-venv && \
    /opt/bonsai-venv/bin/python -m pip install --no-cache-dir \
    openvino==2026.2.0 openvino-genai==2026.2.0.0

COPY verify_bonsai.py server.py smoke.py /opt/bonsai/
WORKDIR /opt/bonsai
ENV PATH="/opt/bonsai-venv/bin:${PATH}"
ENV PYTHONPATH=""
ENTRYPOINT ["/opt/bonsai-venv/bin/python", "-u", "/opt/bonsai/server.py"]
