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

### 1. 安装系统依赖

**必需的系统工具：**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install ffmpeg libsndfile1

# CentOS/RHEL
sudo yum install ffmpeg libsndfile

# macOS
brew install ffmpeg libsndfile
```

### 2. 安装 Python 依赖

```bash
pip install -U pip
pip install -r requirements.txt
# 或者
pip install -e .
```

### 3. 启动服务

```bash
uvicorn main:app --app-dir app --host 0.0.0.0 --port 8090
```

服务启动后访问：
- 健康检查：http://localhost:8090/audio/health
- API 文档：http://localhost:8090/docs

### API 端点

#### 1. 健康检查

**GET `/audio/health`**

请求：
```bash
curl http://localhost:8090/audio/health
```

响应：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "start_time": "2026-01-23 10:00:00",
  "uptime_seconds": 3600,
  "uptime_formatted": "1h 0m 0s",
  "total_requests": 1250,
  "success_count": 1180,
  "failed_count": 70,
  "processing_count": 5,
  "processing_ids": ["audio1_a1b2c3d4", "audio2_x9y8z7w6"],
  "queued_count": 0,
  "queued_ids": []
}
```

#### 2. 音频质检

**POST `/v1/audio/qc`**

请求参数：
- `audio_file` (file, required): 音频文件（支持 mp3/wav/aac/m4a 等格式）
- `task_id` (string, optional): 自定义任务 ID，不传则自动生成

请求示例：
```bash
curl -X POST http://localhost:8090//audio/qc \
  -F "audio_file=@audio.mp3"

# 带自定义 task_id
curl -X POST http://localhost:8090//audio/qc \
  -F "audio_file=@audio.wav" \
  -F "task_id=my_custom_id_123"
```

成功响应（status_code=200）：
```json
{
  "request_id": "audio_a1b2c3d4",
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
  "request_id": "audio_a1b2c3d4",
  "status_code": 1003,
  "data": {}
}
```

**注意**：`request_id` 格式为 `文件名_8位随机字符`（如 `audio_a1b2c3d4`），若传递 `task_id` 参数则使用自定义 ID。

### 配置文件

编辑 `config.toml` 自定义参数：

```toml
[server]
version = "1.0.0"              # 服务版本号
log_level = "INFO"             # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
threadpool_workers = 20        # CPU 线程池大小（FFmpeg 解码）
gpu_infer_concurrency = 1      # GPU 并发限制（VAD 推理最多 N 个请求）

[audio_qc]
vad_model = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"  # 或本地路径
device = "cuda:0"              # "cuda:0", "cuda:1", "cuda:2" 或 "cpu"
vad_num_workers = 1            # VAD 进程池大小（推荐与 gpu_infer_concurrency 相同）
return_segments = true         # 是否返回 VAD 分段结果
merge_gap_ms = 120             # VAD 分段合并间隔（ms）
silence_dbfs = -50.0           # 静音检测阈值（dBFS）
max_file_size_mb = 300         # 最大文件大小（MB）
min_duration_ms = 10000        # 最小音频时长（ms）
max_duration_ms = 6600000      # 最大音频时长（ms）
need_clarity = true            # 是否需要清晰度检测

[audio_qc.clipping]
clip_threshold = 0.80          # 削波阈值（0-1），越接近 1 检测越严格
min_event_samples = 10         # 最小削波事件长度（样本数），16kHz时10≈0.625ms

[audio_qc.clarity_v1]
# STFT 参数
win_ms = 20.0                  # 窗长
hop_ms = 10.0                  # 步长

# 频段设置
hf_lo_hz = 3000.0              # 高频段下限
hf_hi_hz = 8000.0              # 高频段上限

# SNR 归一化（第一段：越高越好，分数 0->1）
snr_min_db = -5.0              # 第一段下限，对应 0 分
snr_max_db = 10.0              # 第一段上限，对应 1 分
# SNR 归一化（第二段：越高越差，分数 1->0）
snr_min_db2 = 20.0             # 第二段下限，对应 1 分
snr_max_db2 = 35.0             # 第二段上限，对应 0 分

# 高频能量比归一化（第一段：0->hf_ref 越高越好，分数 0->1）
hf_ref = 0.02                  # 第一段上限，对应 1 分
# 高频能量比归一化（第二段：hf_ref2_l->hf_ref2_h 越高越差，分数 1->0）
hf_ref2_l = 0.02               # 第二段下限，对应 1 分
hf_ref2_h = 0.06               # 第二段上限，对应 0 分

flat_ref = 0.10                # 谱平坦度参考值，越平坦越像噪声

# 权重（会自动归一化到和为1）
w_snr = 0.50                   # SNR 权重
w_hf = 0.30                    # 高频能量比权重
w_flat = 0.20                  # 谱平坦度权重
```

## 并发架构

三层并发模型：
1. **HTTP 层**：Uvicorn 异步处理无限并发请求
2. **CPU 层**：ThreadPoolExecutor（`threadpool_workers`）处理 FFmpeg 解码和音频处理
3. **GPU 层**：ProcessPoolExecutor（`vad_num_workers` 个进程）+ Semaphore（`gpu_infer_concurrency`）控制并发

**示例配置：**
- `threadpool_workers = 20`（20个CPU线程）
- `gpu_infer_concurrency = 1`（最多1个请求同时使用GPU）
- `vad_num_workers = 1`（1个VAD推理进程）

**并发流程：**

当 40 个并发请求到达时：
1. 请求 1-20：并发进入 CPU 线程池执行 FFmpeg 解码（20个线程）
2. 请求 1：解码完成后获取 GPU 信号量，提交到 VAD 进程推理
3. 请求 2-20：解码完成后排队等待 GPU 信号量释放
4. 请求 21-40：等待 CPU 线程池有可用线程

各进程独立加载模型，完全隔离，无线程竞争。

## 日志

日志既输出到控制台，也保存到 `logs/` 目录。日志级别在 `config.toml` 中配置：

```toml
[server]
log_level = "INFO"             # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
```

日志文件自动按日期轮转，保存在项目根目录的 `logs/app.log`。

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
| request_id | string | 请求唯一标识（格式：文件名_8位随机字符，或自定义 task_id） |
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

