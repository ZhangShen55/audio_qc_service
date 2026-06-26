# 混淆版 Docker 部署说明

本项目的固定部署入口已经收敛到 `docker/` 目录：

- `docker/Dockerfile`
- `docker/compose.yml`

固定镜像名：

```bash
jy-algorithm-app-audio-qc:v1.0.0-cuda-amd64
```

固定运行配置挂载路径：

```bash
/root/config/config_audio_qc.toml:/srv/app/config.toml:ro
```

以下命令都在仓库根目录执行。

## 构建镜像

```bash
docker build -f docker/Dockerfile -t jy-algorithm-app-audio-qc:v1.0.0-cuda-amd64 .
```

这个 `Dockerfile` 已经固化以下内容：

- 构建阶段使用 `python:3.11-slim`。
- 运行阶段使用 `pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime`。
- PyTorch 使用 `torch==2.6.0+cu118` 和 `torchaudio==2.6.0+cu118`。
- 普通依赖从 `https://pypi.org/simple` 安装。
- PyArmor 使用免费版可用的 `basic` 模式。
- 服务端口固定为 `8090`。

## Docker Run 运行

先确保宿主机配置文件存在：

```bash
ls -l /root/config/config_audio_qc.toml
```

启动容器：

```bash
docker rm -f audio-qc-obfuscated >/dev/null 2>&1 || true

docker run -d \
  --name audio-qc-obfuscated \
  -p 8090:8090 \
  -v /root/config/config_audio_qc.toml:/srv/app/config.toml:ro \
  jy-algorithm-app-audio-qc:v1.0.0-cuda-amd64
```

查看日志：

```bash
docker logs -f audio-qc-obfuscated
```

停止容器：

```bash
docker rm -f audio-qc-obfuscated
```

## Docker Compose 运行

首次构建并启动：

```bash
docker compose -f docker/compose.yml up -d --build
```

已有镜像时直接启动：

```bash
docker compose -f docker/compose.yml up -d
```

查看日志：

```bash
docker compose -f docker/compose.yml logs -f audio-qc
```

停止容器：

```bash
docker compose -f docker/compose.yml down
```

## 健康检查

```bash
curl http://127.0.0.1:8090/audio/health
```

## GPU 运行

当前固定运行命令默认不把 GPU 暴露给容器，等价于原来的 `GPU=0`。

如果要让容器访问 GPU，需要同时满足：

- 宿主机已安装 NVIDIA 驱动。
- Docker 已安装 NVIDIA container runtime。
- 配置文件中使用 CUDA 设备，例如：

```toml
[audio_qc]
device = "cuda:0"
```

Docker Run 启用 GPU：

```bash
docker rm -f audio-qc-obfuscated >/dev/null 2>&1 || true

docker run -d \
  --name audio-qc-obfuscated \
  --gpus all \
  -p 8090:8090 \
  -v /root/config/config_audio_qc.toml:/srv/app/config.toml:ro \
  jy-algorithm-app-audio-qc:v1.0.0-cuda-amd64
```

Docker Compose 启用 GPU：打开 `docker/compose.yml`，取消下面这一行的注释：

```yaml
    gpus: all
```

然后执行：

```bash
docker compose -f docker/compose.yml up -d
```

## 代码保护方式

本镜像构建时会在 Linux 容器内运行 PyArmor，最终镜像只复制混淆后的应用上下文。

保护方式：

- `app/main.py`、`app/api/*.py` 等入口文件保留稳定 import 路径，保证 FastAPI 和 Uvicorn 正常启动。
- 受保护实现模块会移动到内部包 `_x`。
- 内部实现文件名会变成 4 到 6 位小写字母。
- 原模块路径只保留兼容包装模块。
- 最终运行镜像不复制受保护模块的原始源码。

本方案不使用 outer key 授权；默认使用 PyArmor 免费版可用的 `basic` 混淆模式。

## 高级入口

`docker/build.sh`、`docker/run.sh`、`docker/verify.sh` 和 `docker/Dockerfile.obfuscated` 仍保留给调试或非固定环境使用。

日常部署请优先使用 `docker/Dockerfile` 和 `docker/compose.yml`，避免再维护大量环境变量参数。
