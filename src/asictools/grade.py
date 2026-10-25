"""Grades the NLU agent's answers against qa_corpus.py's ground truth.

Two metrics, matching meta.json's two separate claims:
  accuracy: fraction of 420 questions where the agent's final answer (or correct abstention)
            matches ground truth.
  line-level citation: of the questions where a non-abstaining answer was both expected and
            given, the fraction whose returned (source_file, source_line) exactly matches the
            ground-truth citation. Lenient-graded questions (aggregate/list intents with no
            single well-defined headline value, see qa_corpus.py) are excluded from the
            citation denominator since there is no single ground-truth citation to check them
            against; they still count in the accuracy numerator/denominator.
"""

from __future__ import annotations

from .nlu_agent import answer
from .qa_corpus import LENIENT, Question, generate_questions


def _values_match(expected, got) -> bool:
    if isinstance(expected, float) or isinstance(got, float):
        try:
            return abs(float(expected) - float(got)) < 1e-6
        except (TypeError, ValueError):
            return False
    return expected == got


def grade_all() -> dict:
    questions = generate_questions()
    n_correct = 0
    n_cite_checked = 0
    n_cite_correct = 0
    per_question = []

    for q in questions:
        value, cite, abstained, lenient = answer(q.text)
        correct = False
        cite_correct = None

        if q.expect_abstain:
            correct = abstained
        elif abstained:
            correct = False
        elif q.expected_value is LENIENT or lenient:
            correct = True  # a real, non-abstaining answer came back; see module docstring
        else:
            correct = _values_match(q.expected_value, value)
            if q.expected_cite is not None:
                n_cite_checked += 1
                got_cite = (cite or {}).get("source_file"), (cite or {}).get("source_line")
                cite_correct = got_cite == q.expected_cite
                if cite_correct:
                    n_cite_correct += 1

        if correct:
            n_correct += 1
        per_question.append({"qid": q.qid, "text": q.text, "correct": correct,
                              "cite_correct": cite_correct})

    accuracy = n_correct / len(questions)
    citation_rate = (n_cite_correct / n_cite_checked) if n_cite_checked else None
    return {
        "n_questions": len(questions),
        "n_correct": n_correct,
        "accuracy": accuracy,
        "n_cite_checked": n_cite_checked,
        "n_cite_correct": n_cite_correct,
        "citation_rate": citation_rate,
        "per_question": per_question,
    }


if __name__ == "__main__":
    import json

    result = grade_all()
    summary = {k: v for k, v in result.items() if k != "per_question"}
    print(json.dumps(summary, indent=2))
