import numpy as np
from services.metrics.silence import is_silent_by_frames


def test_silence_true():
    x = np.zeros(16000 * 2, dtype=np.float32)  # 2 seconds
    assert is_silent_by_frames(x, sr=16000, silence_dbfs=-60.0)


def test_silence_false():
    # low but audible sine
    t = np.linspace(0, 2.0, 16000 * 2, endpoint=False)
    x = (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    assert not is_silent_by_frames(x, sr=16000, silence_dbfs=-60.0)
