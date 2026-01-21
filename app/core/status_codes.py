# app/core/status_codes.py

# 成功
OK = 200

# 输入类
MISSING_AUDIO = 1001          # file 缺失或空文件
DURATION_OUT_OF_RANGE = 1002  # 不在 [min_duration_ms, max_duration_ms]
FILE_TOO_LARGE = 1003         # 超过 max_file_size_mb

# 解码与重采样
DECODE_FAILED = 2001          # ffmpeg/codec 解码失败
RESAMPLE_FAILED = 2002        # 无法重采样到 mono16k
INVALID_AUDIO = 2003          # 音频数据异常（NaN/Inf/无有效样本）

# 处理链路
VAD_INFER_FAILED = 3001       # VAD 推理异常

