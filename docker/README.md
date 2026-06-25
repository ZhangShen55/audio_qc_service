# 混淆版 Docker 部署说明

本目录提供音频质检服务的混淆版 Docker 部署方案，最终镜像名称为：

```bash
jy-algorithm-app-audio-qc:v1.0.0
```

默认构建 CPU 镜像。GPU 部署可通过覆盖 PyTorch 轮子参数实现，运行环境需要 Linux 主机、NVIDIA 驱动和 NVIDIA container runtime。

## 前置要求

- Docker 29+，或兼容的 Docker Engine。
- 构建主机可使用 Python 3。
- 构建 Docker 镜像时可以访问网络，用于安装 Python 依赖。
- 可选：在本机 conda 环境 `audio_qc` 中安装 PyArmor，用于本地预检查。
- GPU 部署需要 NVIDIA 驱动、NVIDIA container runtime，以及匹配 CUDA 版本的 PyTorch 轮子参数。

本方案不使用 outer-key 授权。PyArmor 只作为构建期源码保护步骤使用。

默认模式兼容 PyArmor 免费版/试用版：

```bash
PYARMOR_MODE=basic docker/build.sh
```

该模式把 PyArmor basic 混淆、内部实现文件随机命名、兼容包装模块结合起来使用。没有 Pro 授权时，这是当前方案中可用的最强保护方式。

Dockerfile 会在 Linux 构建阶段安装并运行 PyArmor。这样做是必要的，因为 macOS 上生成的 PyArmor 运行时不能直接复制到 Linux 容器中使用。最终运行阶段只复制 Linux 构建阶段生成的混淆应用上下文。

如果后续在自定义 builder 流程中注册了 PyArmor Pro，并且需要启用 RFT，可使用：

```bash
PYARMOR_MODE=pro PYARMOR_ENABLE_RFT=1 docker/build.sh
```

## 在 Conda 中安装 PyArmor

Docker 镜像构建会在 Linux 构建阶段自行安装 PyArmor。本地安装脚本是可选的，主要用于本地命令行预检查；脚本会优先查找 `PATH` 中的 `pyarmor`，找不到时再尝试 conda 环境 `audio_qc`。

安装到 `audio_qc`：

```bash
docker/install_pyarmor.sh
```

也可以手动安装：

```bash
conda activate audio_qc
python -m pip install -U pyarmor
```

如果需要 Pro/RFT 模式，可选注册 PyArmor Pro：

```bash
conda run -n audio_qc pyarmor reg /path/to/pyarmor-regfile.zip
```

验证 PyArmor：

```bash
conda run -n audio_qc pyarmor --version
```

使用 `PYARMOR_MODE=pro` 时，输出需要显示支持 RFT，例如 `RFT Mode: Yes`。试用授权通常显示 `RFT Mode: No`，因此没有 Pro 注册时请保持默认 `PYARMOR_MODE=basic`。

如需使用其他 conda 环境：

```bash
PYARMOR_CONDA_ENV=my_env docker/build.sh
```

## 文件说明

- `Dockerfile.obfuscated`：混淆版镜像的 Dockerfile。
- `prepare_obfuscated_app.py`：生成干净的混淆构建上下文。
- `build.sh`：构建临时镜像、验证、打最终标签，并清理临时镜像。
- `run.sh`：从指定镜像标签启动容器。
- `verify.sh`：验证健康检查、音频质检接口，以及受保护源码是否不存在。
- `cleanup.sh`：只清理本项目的临时容器和临时镜像 tag。
- `requirements-runtime.txt`：运行时 Python 依赖，不包含 Torch/Torchaudio。

## 保护模型

FastAPI 和 Uvicorn 需要稳定的 import 路径和路由签名。因此 `app/main.py`、`app/api/*.py` 等入口文件会作为较薄的稳定模块保留。

受保护的实现模块会被复制到内部包 `_x`，并使用 4 到 6 位小写字母文件名。原模块路径会变成兼容包装模块，例如：

```python
# 生成的兼容包装模块；受保护实现位于 _x.abcde
from _x.abcde import *
```

随后 PyArmor 会混淆内部 `_x` 包。这样最终镜像既能保留服务运行所需的 import 路径，又能避免把受保护模块的原始源码放进运行时镜像。

## 构建

在仓库根目录执行：

```bash
docker/build.sh
```

脚本会先构建一个临时验证镜像。只有验证通过后，才会打最终标签：

```bash
jy-algorithm-app-audio-qc:v1.0.0
```

CPU 默认参数：

```bash
TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
TORCH_VERSION=2.7.0+cpu
TORCHAUDIO_VERSION=2.7.0
```

GPU 构建示例：

```bash
TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128 \
TORCH_VERSION=2.7.0+cu128 \
TORCHAUDIO_VERSION=2.7.0+cu128 \
docker/build.sh
```

GPU 容器运行示例：

```bash
GPU=1 docker/run.sh jy-algorithm-app-audio-qc:v1.0.0
```

## 运行

```bash
docker/run.sh jy-algorithm-app-audio-qc:v1.0.0
```

服务默认监听：

```text
http://127.0.0.1:8090
```

覆盖宿主机端口：

```bash
PORT=18090 docker/run.sh jy-algorithm-app-audio-qc:v1.0.0
```

## 验证

```bash
docker/verify.sh jy-algorithm-app-audio-qc:v1.0.0
```

验证内容：

- `/audio/health` 可以响应。
- `/audio/qc` 可以接收脚本生成的 12 秒 WAV 文件，并返回业务 `status_code=200`。
- 运行时镜像中不存在受保护模块的原始源码；受保护的稳定路径必须是生成的包装模块。

手动检查混淆清单：

```bash
docker run --rm jy-algorithm-app-audio-qc:v1.0.0 \
  python -c 'import json; print(json.load(open("/srv/app/obfuscation-manifest.json")))'
```

## 清理

构建成功后：

```bash
docker/cleanup.sh --keep-final
```

该命令只删除本项目的临时标签和容器，并保留：

```bash
jy-algorithm-app-audio-qc:v1.0.0
```

脚本不会执行广泛的 Docker prune，也不会删除无关镜像。

## 故障排查

如果提示 PyArmor 缺失：

```text
混淆版 Docker 构建需要安装 PyArmor
```

请在 conda 环境 `audio_qc` 中安装 PyArmor，然后重新执行 `docker/build.sh`。使用 PyArmor 免费版/试用版时保持默认 `PYARMOR_MODE=basic`。

如果 `PYARMOR_MODE=pro` 下 Pro/RFT 探测失败，请确认已注册的授权支持 RFT。免费版/试用版构建应使用 `PYARMOR_MODE=basic`，该模式会跳过 RFT 探测。

如果健康检查超时，可查看日志：

```bash
docker logs audio-qc-obfuscated-verify
```

CPU 环境中 VAD 模型预热可能较慢，验证脚本会等待一段时间后才判定失败。
