"""A deterministic, rule-based stand-in for an LLM agent deciding which of the 19 tools to call
and reading its answer back out.

This is the actual source of most measured inaccuracy (see README Findings), not the tools:
the tools are exact SQL lookups against the corpus they were generated from and are correct by
construction. This agent classifies a free-text question by a prioritized list of substring
rules (first match wins, the same "ordering can steal a match" failure a hand-rolled intent
router has in practice) and extracts parameters with regex, so a question whose entity name or
phrasing does not match a rule's exact expected shape genuinely fails here, not at the tool. It
is a disclosed stand-in for a real LLM calling these tools, not the tools being graded loosely.

Each rule returns (value, cite, abstained, lenient): `lenient=True` means this question's
intent (an aggregate like "summarize by rule") does not have one well-defined headline value,
and the grader only checks that a real, non-abstaining answer came back.
"""

from __future__ import annotations

import re

from . import server
from .blocks import BLOCKS

_RULES: list[tuple[str, object]] = []


def rule(trigger):
    def deco(fn):
        _RULES.append((trigger, fn))
        return fn
    return deco


def _find_block(text: str) -> str | None:
    for b in BLOCKS:
        if b in text:
            return b
    return None


def _abstained(resp: dict) -> bool:
    return bool(resp.get("abstain"))


@rule("worst slack endpoint")
def _r1(text):
    block = _find_block(text)
    resp = server.get_timing_summary(block) if block else {}
    return resp.get("worst_endpoint"), resp.get("cite"), _abstained(resp), False


@rule("worst-case slack value")
def _r2(text):
    block = _find_block(text)
    resp = server.get_timing_summary(block) if block else {}
    return resp.get("worst_slack_ps"), resp.get("cite"), _abstained(resp), False


@rule("timing violations")
def _r3(text):
    block = _find_block(text)
    if not block:
        return None, None, True, False
    resp = server.list_timing_violations(block)
    return None, None, _abstained(resp), True


@rule("how much slack does endpoint")
def _r4(text):
    block = _find_block(text)
    m = re.search(r"endpoint (\S+) have", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.get_slack_for_endpoint(block, m.group(1))
    return resp.get("slack_ps"), resp.get("cite"), _abstained(resp), False


@rule("critical path detail for")
def _r5(text):
    block = _find_block(text)
    m = re.search(r"critical path detail for (\S+) in", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.get_critical_path(block, m.group(1))
    if _abstained(resp):
        return None, None, True, False
    for r in resp.get("runs", []):
        if r["run_id"] == "tt_0p80v_125c":
            return r["endpoint"], r["cite"], False, False
    return None, None, False, False


@rule("compare timing for endpoint")
def _r6(text):
    block = _find_block(text)
    m = re.search(r"endpoint (\S+) in", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.compare_timing_runs(block, "tt_0p80v_125c", "ff_0p88v_m40c", m.group(1))
    if _abstained(resp):
        return None, None, True, False
    tt = resp.get("tt_0p80v_125c", {})
    return resp.get("endpoint"), tt.get("cite"), False, False


@rule("lint findings in")
def _r7(text):
    block = _find_block(text)
    if not block:
        return None, None, True, False
    m = re.search(r"severity (\w+)", text, re.IGNORECASE)
    resp = server.list_lint_findings(block, severity=m.group(1).upper() if m else None)
    return None, None, _abstained(resp), True


@rule("detail for lint finding")
def _r8(text):
    m = re.search(r"detail for lint finding (\S+)\?", text, re.IGNORECASE)
    if not m:
        return None, None, False, False
    resp = server.get_lint_finding(m.group(1))
    return resp.get("rule"), resp.get("cite"), _abstained(resp), False


@rule("summarize lint findings")
def _r9(text):
    block = _find_block(text)
    if not block:
        return None, None, True, False
    resp = server.lint_summary_by_rule(block)
    return None, None, _abstained(resp), True


@rule("why was lint finding")
def _r10(text):
    m = re.search(r"lint finding (\S+) waived", text, re.IGNORECASE)
    if not m:
        return None, None, False, False
    resp = server.get_lint_waiver(m.group(1))
    return resp.get("waiver_reason"), resp.get("cite"), _abstained(resp), False


@rule("coverage summary for")
def _r11(text):
    block = _find_block(text)
    resp = server.get_coverage_summary(block) if block else {}
    return resp.get("worst_bin"), resp.get("cite"), _abstained(resp), False


@rule("functional coverage holes")
def _r12(text):
    block = _find_block(text)
    resp = server.list_coverage_holes(block, metric="functional") if block else {}
    holes = resp.get("holes", [])
    if not holes:
        return None, None, False, False
    h = holes[0]
    return h.get("bin"), h.get("cite"), False, False


@rule("functional coverage group")
def _r13(text):
    block = _find_block(text)
    m = re.search(r"coverage group (\S+) in", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.get_functional_coverage_group(block, m.group(1))
    return None, None, _abstained(resp), not _abstained(resp)


@rule("below coverage goal")
def _r14(text):
    block = _find_block(text)
    resp = server.list_coverage_below_goal(block) if block else {}
    below = resp.get("below_goal", [])
    if not below:
        return None, None, False, False
    b = below[0]
    return b.get("bin"), b.get("cite"), False, False


@rule("code coverage hit count for")
def _r15(text):
    block = _find_block(text)
    m = re.search(r"for (\S+) line (\d+) in", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.get_code_coverage_line(block, m.group(1), int(m.group(2)))
    return resp.get("hit_count"), resp.get("cite"), _abstained(resp), False


@rule("commit history for")
def _r16(text):
    block = _find_block(text)
    m = re.search(r"commit history for (\S+) in", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.get_file_history(block, m.group(1))
    return None, None, _abstained(resp), not _abstained(resp)


@rule("what is commit")
def _r17(text):
    m = re.search(r"what is commit (\S+) in", text, re.IGNORECASE)
    if not m:
        return None, None, False, False
    resp = server.get_commit(m.group(1))
    return resp.get("message"), resp.get("cite"), _abstained(resp), False


@rule("diff commits")
def _r18(text):
    block = _find_block(text)
    m = re.search(r"diff commits (\S+) and (\S+) in", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    commit_a = m.group(1)
    resp = server.diff_commits(block, commit_a, m.group(2))
    if _abstained(resp):
        return None, None, True, False
    detail = resp.get(commit_a, {})
    return detail.get("message"), detail.get("cite"), False, False


@rule("who last touched")
def _r19(text):
    block = _find_block(text)
    m = re.search(r"who last touched (\S+) in", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.blame_line(block, m.group(1), 0)
    return None, None, _abstained(resp), not _abstained(resp)


@rule("mention")
def _r20(text):
    block = _find_block(text)
    m = re.search(r"mention (\w+)\?", text, re.IGNORECASE)
    if not (block and m):
        return None, None, False, False
    resp = server.list_commits_touching_keyword(block, m.group(1))
    return None, None, _abstained(resp), not _abstained(resp)


def answer(question_text: str):
    """Returns (value, cite, abstained, lenient).

    Trigger matching is case-insensitive (the question's wording, not its entity names, decides
    intent), but every rule's regex extraction runs against the original-cased text: entity
    names in this corpus (endpoint pin suffixes like `/D`, hex-flavored commit ids) are
    case-sensitive, and a first version of this agent lowercased before extraction too, which
    silently broke exact-match lookups for every entity name containing an uppercase character
    (see README Findings).
    """
    lowered = question_text.lower()
    for trigger, fn in _RULES:
        if trigger in lowered:
            return fn(question_text)
    return None, None, False, False
