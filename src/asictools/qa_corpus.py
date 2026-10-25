"""Generates 420 natural-language questions with ground truth, drawn from the real corpus.

Each question names a tool-shaped intent in English, not a structured tool call; `nlu_agent.py`
has to classify which of the 19 tools answers it and extract parameters from the sentence
before it can even call a tool, which is where most of the measured inaccuracy comes from (see
README Findings), not from the tools themselves (those are exact SQL lookups against the
corpus they were generated from).

A deliberate fraction of questions ask about a plausible but non-existent entity, so the right
answer is to abstain; the grader counts correctly abstaining as a correct answer. A few intents
(aggregate summaries, "who last touched", "diff two commits") are graded leniently by
grade.py, disclosed there, because their "one headline value" is less well-defined than a
single-row lookup's.

Fixed seed 20261102, independent of generate_corpus.py's own seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from .blocks import BLOCKS
from .generate_corpus import Corpus, generate_corpus

SEED = 20261102
N_QUESTIONS = 420
LENIENT = object()  # sentinel: this question's "expected_value" is not strictly checkable


@dataclass
class Question:
    qid: int
    text: str
    expect_abstain: bool
    expected_value: object
    expected_cite: tuple | None


def _gen_for_block(block: str, corpus: Corpus, rng: random.Random) -> list[Question]:
    qs: list[Question] = []
    timing = [r for r in corpus.timing if r.block == block and r.run_id == "tt_0p80v_125c"]
    lint = [r for r in corpus.lint if r.block == block]
    fcov = [r for r in corpus.cov_functional if r.block == block]
    ccov = [r for r in corpus.cov_code if r.block == block]
    rev = [r for r in corpus.revision if r.block == block]

    def add(text, expect_abstain, value, cite):
        qs.append(Question(0, text, expect_abstain, value, cite))

    # Timing
    if timing:
        worst = min(timing, key=lambda r: r.slack_ps)
        add(f"What is the worst slack endpoint in {block}'s timing report?", False,
            worst.endpoint, (worst.source_file, worst.source_line))
        add(f"What is the worst-case slack value for {block}?", False,
            worst.slack_ps, (worst.source_file, worst.source_line))
        add(f"List the timing violations in {block}.", False, LENIENT, None)
        for r in rng.sample(timing, min(4, len(timing))):
            add(f"How much slack does endpoint {r.endpoint} have in {block}?", False,
                r.slack_ps, (r.source_file, r.source_line))
        for r in rng.sample(timing, min(4, len(timing))):
            add(f"What is the critical path detail for {r.path_id} in {block}?", False,
                r.endpoint, (r.source_file, r.source_line))
        for r in rng.sample(timing, min(2, len(timing))):
            add(f"Compare timing for endpoint {r.endpoint} in {block} between tt_0p80v_125c and ff_0p88v_m40c.",
                False, r.endpoint, (r.source_file, r.source_line))
        add(f"What is the critical path detail for {block}_path_999 in {block}?", True, None, None)
        add(f"How much slack does endpoint {block}_u/reg_nonexistent/D have in {block}?", True, None, None)

    # Lint
    if lint:
        for r in rng.sample(lint, min(4, len(lint))):
            add(f"List the lint findings in {block} with severity {r.severity}.", False,
                LENIENT, None)
        for r in rng.sample(lint, min(4, len(lint))):
            add(f"What is the detail for lint finding {r.finding_id}?", False,
                r.rule, (r.source_file, r.source_line))
        add(f"Summarize lint findings by rule for {block}.", False, LENIENT, None)
        waived = [r for r in lint if r.waived]
        for r in rng.sample(waived, min(2, len(waived))):
            add(f"Why was lint finding {r.finding_id} waived?", False,
                r.waiver_reason, (r.source_file, r.source_line))
        not_waived = [r for r in lint if not r.waived]
        for r in rng.sample(not_waived, min(2, len(not_waived))):
            add(f"Why was lint finding {r.finding_id} waived?", True, None, None)
        add("What is the detail for lint finding nonexistent_finding_999?", True, None, None)

    # Coverage
    if fcov:
        worst = min(fcov, key=lambda r: r.hit_count)
        add(f"What is the coverage summary for {block}?", False,
            f"{worst.group_name}.{worst.bin_name}", (worst.source_file, worst.source_line))
        holes = [r for r in fcov if r.hit_count == 0]
        for _ in range(min(2, len(holes))):
            add(f"List the functional coverage holes in {block}.", False, LENIENT, None)
        groups = list({r.group_name for r in fcov})
        for g in rng.sample(groups, min(2, len(groups))):
            add(f"Show the functional coverage group {g} in {block}.", False, LENIENT, None)
        below = [r for r in fcov if r.hit_count < r.goal]
        for _ in range(min(2, len(below))):
            add(f"Which bins are below coverage goal in {block}?", False, LENIENT, None)
    if ccov:
        for r in rng.sample(ccov, min(3, len(ccov))):
            add(f"What is the code coverage hit count for {r.rtl_file} line {r.rtl_line} in {block}?",
                False, r.hit_count, (r.source_file, r.source_line))
    add(f"What is the code coverage hit count for rtl/{block}_nonexistent.sv line 9999 in {block}?",
        True, None, None)

    # Revision history
    if rev:
        for r in rng.sample(rev, min(2, len(rev))):
            add(f"What is the commit history for {r.rtl_file} in {block}?", False, LENIENT, None)
        for r in rng.sample(rev, min(3, len(rev))):
            add(f"What is commit {r.commit_id} in {block}?", False,
                r.message, (r.source_file, r.source_line))
        for _ in range(min(2, len(rev) // 2)):
            r3, r4 = rng.sample(rev, 2)
            add(f"Diff commits {r3.commit_id} and {r4.commit_id} in {block}.", False,
                r3.message, (r3.source_file, r3.source_line))
        for r in rng.sample(rev, min(2, len(rev))):
            add(f"Who last touched {r.rtl_file} in {block}?", False, LENIENT, None)
        for kw in ("fifo", "counter", "onehot"):
            matches = [r for r in rev if kw in r.message]
            if matches:
                # LENIENT: this corpus's small fixed pool of commit messages means several
                # commits in the same block often share the same keyword, so "which commits
                # mention X" has no single well-defined ground-truth commit id, the same
                # reason list_coverage_holes/list_coverage_below_goal questions are LENIENT.
                add(f"Which commits in {block} mention {kw}?", False, LENIENT, None)
        add(f"What is commit {block}_nonexistent_commit in {block}?", True, None, None)

    return qs


# A first version of this corpus used only one canonical phrasing per intent, and nlu_agent's
# regex rules (written against those exact phrasings) scored a suspicious 100%/100%: a trivial
# result, since the agent was graded on sentences shaped exactly like the rules expecting them,
# not evidence the rule-based approach generalizes. PARAPHRASES swaps in a synonym for one
# trigger-critical word in ~30% of questions (fixed by the same seeded rng, not cherry-picked
# per question), so the agent's substring rules genuinely miss some of them, the same way a
# real rule-based NLU would on wording it was not written for. See README Findings.
_PARAPHRASES = [
    ("endpoint", "pin"),
    ("slack", "timing margin"),
    ("List the", "Show me the"),
    ("What is", "Could you tell me"),
    ("coverage", "verification coverage"),
    ("commit", "changelist"),
    ("mention", "reference"),
    ("Who last touched", "Who most recently modified"),
]
PARAPHRASE_RATE = 0.3


def _maybe_paraphrase(text: str, rng: random.Random) -> str:
    if rng.random() >= PARAPHRASE_RATE:
        return text
    candidates = [(a, b) for a, b in _PARAPHRASES if a in text]
    if not candidates:
        return text
    a, b = rng.choice(candidates)
    return text.replace(a, b, 1)


def generate_questions() -> list[Question]:
    corpus = generate_corpus(Path("data/qa_reports_scratch"))
    rng = random.Random(SEED)
    all_qs: list[Question] = []
    for block in BLOCKS:
        all_qs.extend(_gen_for_block(block, corpus, rng))
    rng.shuffle(all_qs)
    if len(all_qs) < N_QUESTIONS:
        raise RuntimeError(f"only generated {len(all_qs)} questions, need {N_QUESTIONS}")
    all_qs = all_qs[:N_QUESTIONS]
    return [Question(i + 1, _maybe_paraphrase(q.text, rng), q.expect_abstain, q.expected_value,
                     q.expected_cite)
            for i, q in enumerate(all_qs)]
