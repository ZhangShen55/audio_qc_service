# audio_qc_service

FastAPI 音频质检服务：
- 输入：multipart/form-data 上传音频文件（mp3/wav/aac…）
- 预处理：ffmpeg 解码并重采样到 mono 16kHz wav
- VAD：FunASR AutoModel（FSMN VAD）
- 输出：静音/人声/人声占比/爆音次数/清晰度（V1规则版）+ 可选 VAD 分段
- 协议：HTTP 永远 200，业务码在 `status_code` 字段；非 200 时 `data={}`

## Run
```bash
pip install -U pip
pip install -e .

# 需要系统安装 ffmpeg
# yum/apt 安装即可

uvicorn main:app --app-dir app --host 0.0.0.0 --port 8000

# API
POST /v1/audio/qc
- form-data: file=@xxx.mp3

成功：
```json
{"request_id":"...","status_code":200,"data":{...}}
```

失败：
```json
{"request_id":"...","status_code":1003,"data":{}}
```

