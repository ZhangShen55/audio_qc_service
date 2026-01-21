# Audio QC API

## Endpoint
POST `/v1/audio/qc`

### Request
- Content-Type: `multipart/form-data`
- Field:
  - `file`: audio file (mp3/wav/aac/...)

### Response (HTTP always 200)
```json
{
  "request_id": "uuid/雪花id",
  "status_code": 200,
  "data": {}
}
```
- status_code == 200 => data has full fields
- status_code != 200 => data is {}

## status_code
- 200: OK
- 1001: 音频文件缺失/空
- 1002: 音频文件时间过短/过长
- 1003: 文件太大 M
- 2001: 解码失败 (ffmpeg/codec)
- 2002: 重采样失败
- 2003: 不可用的音频文件格式 (NaN/Inf/empty samples)
- 3001: VAD 推断失败

## Success data schema
```json
{
  "is_silent": false,
  "has_speech": true,
  "speech_ratio": 0.63,
  "clip_count": 2,
  "clarity": 78.4,
  "clarity_detail": {
    "snr_db": 18.2,
    "hf_ratio": 0.21,
    "spectral_flatness": 0.12
  },
  "vad": {
    "segments_ms": [[120, 980], [1500, 4200]],
    "speech_ms": 3560
  }
}
```
### Notes
- `speech_ratio` is clamped to `[0,1]` 保留4位小数.
- If `need_clarity=false` in config, `clarity=null` and `clarity_detail=null`.
- If `return_segments=false` in config, `vad.segments_ms=[]` but `vad.speech_ms` is still returned.

