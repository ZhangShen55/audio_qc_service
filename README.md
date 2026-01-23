# audio_qc_service

FastAPI 音频质检服务：
- 输入：multipart/form-data 上传音频文件（mp3/wav/aac…）
- 预处理：ffmpeg 解码并重采样到 mono 16kHz wav
- VAD：FunASR AutoModel（FSMN VAD，多进程并发推理）
- 输出：
  - `is_silent`: 静音检测
  - `has_speech`: 人声检测
  - `speech_ratio`: 人声占比
  - `has_clip`: 削波检测
  - `clip_detail`: 削波详情（削波次数 + 时间点列表）
  - `clarity`: 清晰度分数（V1规则版）
  - `clarity_detail`: 清晰度详情（SNR + 高频比 + 谱平坦度）
  - `vad`: VAD 分段结果（可选返回）
- 协议：HTTP 永远 200，业务码在 `status_code` 字段；非 200 时 `data={}`

## 快速开始

### 安装依赖
```bash
pip install -U pip
pip install -e .

# 需要系统安装 ffmpeg
# Ubuntu: sudo apt install ffmpeg
# CentOS/RHEL: sudo yum install ffmpeg
```

### 启动服务
```bash
uvicorn main:app --app-dir app --host 0.0.0.0 --port 8090
```

### API 端点

#### 1. 健康检查

**GET `/v1/audio/health`**

请求：
```bash
curl http://localhost:8090/v1/audio/health
```

响应：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "total_requests": 1250,
  "success_count": 1180,
  "failed_count": 70,
  "processing_count": 5
}
```

#### 2. 音频质检

**POST `/v1/audio/qc`**

请求参数：
- `audio_file` (file, required): 音频文件（支持 mp3/wav/aac/m4a 等格式）
- `task_id` (string, optional): 自定义任务 ID，不传则自动生成

请求示例：
```bash
curl -X POST http://localhost:8090/v1/audio/qc \
  -F "audio_file=@audio.mp3"

# 带自定义 task_id
curl -X POST http://localhost:8090/v1/audio/qc \
  -F "audio_file=@audio.mp3" \
  -F "task_id=my_custom_id_123"
```

成功响应（status_code=200）：
```json
{
  "request_id": "4555b8e8d82846ffa694dd83210626aa",
  "status_code": 200,
  "data": {
    "is_silent": false,
    "has_speech": true,
    "speech_ratio": 0.3779,
    "has_clip": true,
    "clip_detail": {
      "clip_count": 10,
      "times_ms": [100, 500, 1200, 2000, 3500, 4100, 5200, 6000, 7300, 8500]
    },
    "clarity": 90.6276,
    "clarity_detail": {
      "snr_db": 14.0525,
      "hf_ratio": 0.062467,
      "spectral_flatness": 0.046862
    },
    "vad": {
      "segments_ms": [[0, 5000], [10000, 15000]],
      "speech_ms": 10000
    }
  }
}
```

失败响应（status_code!=200）：
```json
{
  "request_id": "4555b8e8d82846ffa694dd83210626aa",
  "status_code": 1003,
  "data": {}
}
```

### 配置文件

编辑 `config.toml` 自定义参数：

```toml
[server]
threadpool_workers = 20        # CPU 线程池大小（FFmpeg 解码）
gpu_infer_concurrency = 4      # GPU 并发限制（VAD 推理最多 N 个请求）

[audio_qc]
vad_model = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
device = "cuda:0"              # "cuda:0" 或 "cpu"
vad_num_workers = 4            # VAD 进程数（进程池大小）

max_file_size_mb = 300         # 最大文件大小（MB）
min_duration_ms = 10000        # 最小音频时长（ms）
max_duration_ms = 6600000      # 最大音频时长（ms）

[audio_qc.clipping]
clip_threshold = 0.99          # 削波阈值（0-1），越接近 1 越严格
min_event_samples = 10         # 最小削波事件长度（样本数）

[audio_qc.clarity_v1]
snr_target_db = 18.0
hf_ratio_target = 0.05
```

## 并发架构

三层并发模型：
1. **HTTP 层**：Uvicorn 异步处理无限并发请求
2. **CPU 层**：ThreadPoolExecutor（`threadpool_workers`）处理 FFmpeg 解码和音频处理
3. **GPU 层**：ProcessPoolExecutor（`vad_num_workers` 个进程）+ Semaphore（`gpu_infer_concurrency`）控制并发

当 40 个并发请求到达时，行为如下：
- 请求 1-20：并发进入 CPU 线程池解码
- 请求 1-4：解码完成后进入 GPU VAD 推理阶段（受 Semaphore 限制）
- 请求 5-20：等待 VAD Semaphore 释放
- 请求 21-40：等待 CPU 线程池有可用线程

## 日志

日志既输出到控制台，也保存到 `app/logs/` 目录：

```toml
[logging]
level = "INFO"                 # 日志级别：DEBUG, INFO, WARNING, ERROR
console_enabled = true         # 控制台输出
file_enabled = true            # 文件输出
file_max_bytes = 10485760      # 日志文件大小（10MB）
file_backup_count = 5          # 保留备份文件数
```

## API 文档

### 错误码说明

| 错误码 | 错误说明 | 分类 |
|--------|---------|------|
| 200 | 成功 | 成功 |
| 1001 | 缺少音频文件或文件为空 | 输入类错误 |
| 1002 | 音频时长超出范围 | 输入类错误 |
| 1003 | 文件大小超过限制 | 输入类错误 |
| 2001 | FFmpeg 解码失败 | 解码类错误 |
| 2002 | 重采样失败 | 解码类错误 |
| 2003 | 音频数据异常 | 解码类错误 |
| 3001 | VAD 推理失败 | 处理类错误 |

### 响应参数说明

#### 顶层响应结构

| 参数名 | 类型 | 说明 |
|--------|------|------|
| request_id | string | 请求唯一标识（UUID 或自定义 task_id） |
| status_code | int | 业务状态码（200=成功，其他=失败） |
| data | object | 业务数据（成功时有值，失败时为空对象 `{}`） |

#### data 对象（status_code=200 时）

| 参数名 | 类型 | 说明 |
|--------|------|------|
| is_silent | boolean | 是否为静音音频 |
| has_speech | boolean | 是否包含人声 |
| speech_ratio | float | 人声占比（0.0 ~ 1.0） |
| has_clip | boolean | 是否检测到削波 |
| clip_detail | object \| null | 削波详情（has_clip=false 时为 null） |
| clarity | float \| null | 清晰度分数（0 ~ 100） |
| clarity_detail | object \| null | 清晰度详情 |
| vad | object | VAD 分段结果 |

#### clip_detail 对象

| 参数名 | 类型 | 说明 |
|--------|------|------|
| clip_count | int | 削波事件总数 |
| times_ms | array[int] | 削波时间点列表（毫秒） |

#### clarity_detail 对象

| 参数名 | 类型 | 说明 |
|--------|------|------|
| snr_db | float | 信噪比（dB） |
| hf_ratio | float | 高频能量占比 |
| spectral_flatness | float | 谱平坦度 |

#### vad 对象

| 参数名 | 类型 | 说明 |
|--------|------|------|
| segments_ms | array[array[int]] | VAD 分段列表 `[[start, end], ...]` |
| speech_ms | int | 总人声时长（毫秒） |

