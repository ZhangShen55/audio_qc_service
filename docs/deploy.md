# Deploy Notes

## Dependencies
- `ffmpeg` required
- `funasr` + `torch` (CUDA build if GPU inference is desired)

## Run
```bash
uvicorn main:app --app-dir app --host 0.0.0.0 --port 8000
```


## GPU
- Set in `config.toml`:
    - `audio_qc.device = "cuda:0"`

- Control GPU inference concurrency per process:
    - server.gpu_infer_concurrency = 1 (recommended)

## Concurrency
- CPU/IO heavy tasks are offloaded to default executor configured by:
    - server.threadpool_workers

- If you run multiple workers, each worker loads its own model copy (GPU memory consideration):
    - `uvicorn main:app --app-dir app --workers 1`


## Limits
- File size limited by `audio_qc.max_file_size_mb` (default 300MB)

- Duration limited by `[audio_qc.min_duration_ms`, `audio_qc.max_duration_ms]`