import os
import tempfile
import wave

import pytest
from fastapi.testclient import TestClient

from main import app


def _make_wav_16k_mono(path: str, seconds: int = 3):
    # 生成一个简单的 16k mono wav（静音）
    sr = 16000
    n = sr * seconds
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * n)


@pytest.mark.skipif(os.getenv("RUN_SMOKE") != "1", reason="set RUN_SMOKE=1 to run")
def test_api_returns_200_http():
    client = TestClient(app)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        _make_wav_16k_mono(f.name, seconds=3)
        files = {"file": ("x.wav", open(f.name, "rb"), "audio/wav")}
        r = client.post("/v1/audio/qc", files=files)

    assert r.status_code == 200
    js = r.json()
    assert "request_id" in js
    assert "status_code" in js
    assert "data" in js
