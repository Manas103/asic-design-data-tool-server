from asictools.grade import grade_all


def test_grade_runs_against_live_corpus_and_meets_a_floor():
    result = grade_all()
    assert result["n_questions"] == 420
    # Measured on this machine: accuracy ~0.90, citation ~0.84 (see docs/measure_report.json).
    # These floors guard against a real regression, not the exact value drifting slightly.
    assert result["accuracy"] > 0.80
    assert result["citation_rate"] > 0.75
    assert result["n_cite_checked"] > 100
