FROM python:3.10-slim

WORKDIR /srv/app

# ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /srv/app/pyproject.toml
COPY app /srv/app/app
COPY config.toml /srv/app/config.toml

# 安装依赖
RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--app-dir", "app", "--host", "0.0.0.0", "--port", "8090"]