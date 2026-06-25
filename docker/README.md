# Obfuscated Docker Deployment

This folder contains the deployment path for the obfuscated audio QC service image:

```bash
jy-algorithm-app-audio-qc:v1.0.0
```

The default build target is CPU. GPU deployment is supported by overriding the PyTorch wheel build arguments on a Linux host with NVIDIA container runtime.

## Prerequisites

- Docker 29+ or a compatible Docker Engine.
- Python 3 on the build host.
- PyArmor installed in conda env `audio_qc` on the build host for optional local preflight.
- Network access for Python package installation during Docker build.
- For GPU deployment: NVIDIA driver, NVIDIA container runtime, and CUDA-compatible PyTorch wheel arguments.

The build does not use outer-key licensing. PyArmor is used as a build-time source protection step.

The default mode is free/trial-compatible:

```bash
PYARMOR_MODE=basic docker/build.sh
```

This combines PyArmor basic obfuscation with this repository's filename randomization and wrapper strategy. It is the strongest mode available without a Pro license.

The Dockerfile installs PyArmor inside a Linux builder stage and runs obfuscation there. This is required because a PyArmor runtime generated on macOS cannot be copied into a Linux container. The final runtime stage copies only the Linux-generated obfuscated application context.

If you later register PyArmor Pro in a custom builder workflow and want RFT, use:

```bash
PYARMOR_MODE=pro PYARMOR_ENABLE_RFT=1 docker/build.sh
```

## Install PyArmor In Conda

The Docker image build installs PyArmor inside the Linux builder stage. The local helper below is optional and is useful for local CLI checks; it looks for `pyarmor` on `PATH` first and falls back to conda env `audio_qc`.

Install PyArmor into `audio_qc`:

```bash
docker/install_pyarmor.sh
```

Or manually:

```bash
conda activate audio_qc
python -m pip install -U pyarmor
```

Optional: register PyArmor Pro if you want RFT mode:

```bash
conda run -n audio_qc pyarmor reg /path/to/pyarmor-regfile.zip
```

Verify:

```bash
conda run -n audio_qc pyarmor --version
```

For `PYARMOR_MODE=pro`, the output must show Pro support for RFT, for example `RFT Mode: Yes`. A trial license shows `RFT Mode: No`, so use the default `PYARMOR_MODE=basic` unless a Pro registration is available.

Use a different conda env:

```bash
PYARMOR_CONDA_ENV=my_env docker/build.sh
```

## Files

- `Dockerfile.obfuscated`: runtime image definition.
- `prepare_obfuscated_app.py`: creates a clean obfuscated build context.
- `build.sh`: prepares, builds, verifies, tags, and cleans the final image.
- `run.sh`: starts a container from an image tag.
- `verify.sh`: verifies health, audio QC behavior, and protected-source absence.
- `cleanup.sh`: removes only this project's temporary containers and image tags.
- `requirements-runtime.txt`: runtime Python dependencies excluding Torch/Torchaudio.

## Protection Model

FastAPI and Uvicorn need stable import paths and route signatures. For that reason, entrypoint files such as `app/main.py` and `app/api/*.py` stay as thin stable modules.

Protected implementation modules are copied into an internal package named `_x` with generated lowercase filenames of 4 to 6 letters. The original module paths become generated compatibility wrappers, for example:

```python
# generated compatibility wrapper; protected implementation lives in _x.abcde
from _x.abcde import *
```

PyArmor then obfuscates the internal `_x` package. This means the final image keeps the import paths needed by the service while avoiding original unobfuscated source for protected modules.

## Build

From the repository root:

```bash
docker/build.sh
```

The script builds a temporary validation image first. It tags `jy-algorithm-app-audio-qc:v1.0.0` only after verification passes.

CPU defaults:

```bash
TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
TORCH_VERSION=2.7.0+cpu
TORCHAUDIO_VERSION=2.7.0
```

GPU example:

```bash
TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128 \
TORCH_VERSION=2.7.0+cu128 \
TORCHAUDIO_VERSION=2.7.0+cu128 \
docker/build.sh
```

Run GPU containers with:

```bash
GPU=1 docker/run.sh jy-algorithm-app-audio-qc:v1.0.0
```

## Run

```bash
docker/run.sh jy-algorithm-app-audio-qc:v1.0.0
```

The service listens on:

```text
http://127.0.0.1:8090
```

Override the host port:

```bash
PORT=18090 docker/run.sh jy-algorithm-app-audio-qc:v1.0.0
```

## Verify

```bash
docker/verify.sh jy-algorithm-app-audio-qc:v1.0.0
```

Verification checks:

- `/audio/health` responds.
- `/audio/qc` accepts a generated 12 second WAV file and returns business `status_code=200`.
- Protected original source files are absent from the runtime image; protected stable paths must be generated wrappers.

Manual inspection:

```bash
docker run --rm jy-algorithm-app-audio-qc:v1.0.0 \
  python -c 'import json; print(json.load(open("/srv/app/obfuscation-manifest.json")))'
```

## Cleanup

After a successful build:

```bash
docker/cleanup.sh --keep-final
```

This removes this project's temporary tags and containers while keeping only:

```bash
jy-algorithm-app-audio-qc:v1.0.0
```

It does not run broad Docker prune commands and does not delete unrelated images.

## Troubleshooting

If PyArmor is missing:

```text
PyArmor is required for obfuscated Docker builds
```

Install PyArmor in conda env `audio_qc`, then rerun `docker/build.sh`. For free/trial PyArmor, keep the default `PYARMOR_MODE=basic`.

If the PyArmor Pro probe fails in `PYARMOR_MODE=pro`, confirm the registered license supports RFT. Free/trial builds should use `PYARMOR_MODE=basic`, which skips the RFT probe.

If health verification times out, inspect logs:

```bash
docker logs audio-qc-obfuscated-verify
```

VAD model warmup can take time on CPU. The verification script waits before failing.
