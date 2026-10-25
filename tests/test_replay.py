"""Exercises the real replay mechanism at a reduced scale (100, not 3,000) to keep a routine
`pytest` run's wall time reasonable; `measure.py` runs the real 3,000-call replay for the
docs/measure_report.json number this README reports."""

from asictools.replay_calls import replay


def test_replay_writes_nothing():
    result = replay(n_calls=100)
    assert result["n_calls"] == 100
    assert result["zero_writes"] is True
    assert result["checksums_before"] == result["checksums_after"]
