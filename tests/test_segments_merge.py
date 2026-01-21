from services.metrics.vad_utils import merge_segments_ms, speech_ms_from_segments


def test_merge_segments_overlap():
    segs = [[0, 1000], [900, 1500], [2000, 2500]]
    merged = merge_segments_ms(segs, merge_gap_ms=0)
    assert merged == [[0, 1500], [2000, 2500]]
    assert speech_ms_from_segments(merged) == 1500 + 500


def test_merge_segments_gap():
    segs = [[0, 1000], [1050, 2000]]
    merged = merge_segments_ms(segs, merge_gap_ms=60)
    assert merged == [[0, 2000]]

    merged2 = merge_segments_ms(segs, merge_gap_ms=40)
    assert merged2 == [[0, 1000], [1050, 2000]]
