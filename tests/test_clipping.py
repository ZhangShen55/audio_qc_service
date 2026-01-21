import numpy as np
from services.metrics.clipping import count_clipping_events


def test_no_clipping():
    x = np.sin(np.linspace(0, 10, 16000)).astype(np.float32) * 0.5
    assert count_clipping_events(x) == 0


def test_clipping_two_events():
    x = np.zeros(2000, dtype=np.float32)
    x[100:200] = 1.0
    x[800:900] = -1.0
    assert count_clipping_events(x, clip_threshold=0.99, min_event_samples=10) == 2


def test_short_run_ignored():
    x = np.zeros(2000, dtype=np.float32)
    x[100:105] = 1.0  # only 5 samples
    assert count_clipping_events(x, clip_threshold=0.99, min_event_samples=10) == 0
