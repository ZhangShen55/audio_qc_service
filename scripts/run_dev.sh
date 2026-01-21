
#!/usr/bin/env bash
set -e

# from project root
export PYTHONUNBUFFERED=1

uvicorn main:app --app-dir app --host 0.0.0.0 --port 8000 --reload
