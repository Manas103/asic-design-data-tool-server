from asictools.qa_corpus import N_QUESTIONS, generate_questions


def test_generates_420_questions_deterministically():
    qs_a = generate_questions()
    qs_b = generate_questions()
    assert len(qs_a) == N_QUESTIONS == 420
    assert [q.text for q in qs_a] == [q.text for q in qs_b]  # fixed seed


def test_a_real_fraction_expects_abstention():
    qs = generate_questions()
    n_abstain = sum(1 for q in qs if q.expect_abstain)
    assert 0.08 < n_abstain / len(qs) < 0.25
