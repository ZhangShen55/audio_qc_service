ARG AUDIO_QC_PLATFORM=linux/amd64

FROM --platform=${AUDIO_QC_PLATFORM} python:3.11-slim AS obfuscator

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /work

# 构建阶段安装 PyArmor，并在 Linux/Python 3.11 环境中生成可运行的混淆产物。
RUN pip install --no-cache-dir -U pip pyarmor

COPY app /work/app
COPY config.toml /work/config.toml
COPY vad_model /work/vad_model
COPY docker/prepare_obfuscated_app.py /work/docker/prepare_obfuscated_app.py
COPY docker/requirements-runtime.txt /work/docker/requirements-runtime.txt

RUN PYARMOR_MODE=basic \
    PYARMOR_ENABLE_RFT=0 \
    OBFUSCATION_SALT=jy-audio-qc-v1.0.0 \
    python docker/prepare_obfuscated_app.py \
        --repo-root /work \
        --build-dir /work/build \
        --mode basic

FROM --platform=${AUDIO_QC_PLATFORM} pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/app/app \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /srv/app

# 运行阶段只安装系统运行库和 Python 运行依赖，不复制原始受保护源码。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=obfuscator /work/build/context/requirements-runtime.txt /tmp/requirements-runtime.txt

RUN python -m pip install --no-cache-dir -U pip \
    && python -m pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu118 \
        --extra-index-url https://pypi.org/simple \
        "torch==2.6.0+cu118" \
        "torchaudio==2.6.0+cu118" \
    && python -m pip install --no-cache-dir \
        --index-url https://pypi.org/simple \
        -r /tmp/requirements-runtime.txt

COPY --from=obfuscator /work/build/context/app /srv/app/app
COPY --from=obfuscator /work/build/context/config.toml /srv/app/config.toml
COPY --from=obfuscator /work/build/context/vad_model /srv/app/vad_model
COPY --from=obfuscator /work/build/context/obfuscation-manifest.json /srv/app/obfuscation-manifest.json

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8090/audio/health >/dev/null || exit 1

CMD ["uvicorn", "main:app", "--app-dir", "app", "--host", "0.0.0.0", "--port", "8090"]
