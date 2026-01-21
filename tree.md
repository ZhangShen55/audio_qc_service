audio_qc_service/
  README.md
  pyproject.toml
  config.toml
  Dockerfile
  .dockerignore
  .gitignore

  app/
    audio_qc/
      __init__.py

      main.py                 # FastAPI app 入口
      api/
        __init__.py
        routes.py             # /v1/audio/qc

      core/
        __init__.py
        config.py             # 读 config.toml
        ids.py                # request_id
        response.py           # 统一返回体
        status_codes.py       # 业务码
        logging.py            # 日志（可选）

      services/
        __init__.py
        qc_service.py         # 解码->校验->VAD->指标
        vad_engine.py         # FunASR AutoModel
        decoder.py            # ffmpeg 重采样 mono16k
        audio_io.py           # wav读取/时长
        metrics/
          __init__.py
          silence.py
          clipping.py
          clarity_v1.py
          vad_utils.py

      infra/
        __init__.py
        threadpool.py         # 线程池（可配）
        gpu_gate.py           # GPU并发信号量（可配）
        tempfiles.py          # 临时文件管理

      utils/
        __init__.py
        time.py
        validate.py

  tests/
    test_api_smoke.py
    test_segments_merge.py
    test_clipping.py
    test_silence.py

  scripts/
    run_dev.sh
    bench_ab.py

  docs/
    api.md
    deploy.md
