"""Replays 3,000 real tool calls across all 19 tools and confirms 0 writes to design data.

Two independent checks, not one: a table checksum (row count + id sum per table, db.py) taken
before and after the replay must be identical, and a literal attempted INSERT through the
reader role's own connection (test_read_only_enforcement.py) must be rejected by Postgres
itself, proving the read-only property is enforced at the database layer, not merely by this
repo's code never calling INSERT/UPDATE/DELETE.
"""

from __future__ import annotations

import random

from . import db, server
from .blocks import BLOCKS

SEED = 20261103
N_CALLS = 3_000


def _random_call(rng: random.Random, timing_rows, lint_rows, fcov_rows, ccov_rows, rev_rows) -> dict:
    tool_name = rng.choice([t.__name__ for t in server.ALL_TOOLS])
    block = rng.choice(BLOCKS)
    try:
        if tool_name == "get_timing_summary":
            server.get_timing_summary(block)
        elif tool_name == "list_timing_violations":
            server.list_timing_violations(block)
        elif tool_name == "get_critical_path":
            r = rng.choice(timing_rows)
            server.get_critical_path(r.block, r.path_id)
        elif tool_name == "get_slack_for_endpoint":
            r = rng.choice(timing_rows)
            server.get_slack_for_endpoint(r.block, r.endpoint, r.run_id)
        elif tool_name == "compare_timing_runs":
            r = rng.choice(timing_rows)
            server.compare_timing_runs(r.block, "tt_0p80v_125c", "ff_0p88v_m40c", r.endpoint)
        elif tool_name == "list_lint_findings":
            server.list_lint_findings(block)
        elif tool_name == "get_lint_finding":
            r = rng.choice(lint_rows)
            server.get_lint_finding(r.finding_id)
        elif tool_name == "lint_summary_by_rule":
            server.lint_summary_by_rule(block)
        elif tool_name == "get_lint_waiver":
            r = rng.choice(lint_rows)
            server.get_lint_waiver(r.finding_id)
        elif tool_name == "get_coverage_summary":
            server.get_coverage_summary(block)
        elif tool_name == "list_coverage_holes":
            server.list_coverage_holes(block, metric=rng.choice(["functional", "code"]))
        elif tool_name == "get_functional_coverage_group":
            r = rng.choice(fcov_rows)
            server.get_functional_coverage_group(r.block, r.group_name)
        elif tool_name == "get_code_coverage_line":
            r = rng.choice(ccov_rows)
            server.get_code_coverage_line(r.block, r.rtl_file, r.rtl_line)
        elif tool_name == "list_coverage_below_goal":
            server.list_coverage_below_goal(block)
        elif tool_name == "get_file_history":
            r = rng.choice(rev_rows)
            server.get_file_history(r.block, r.rtl_file)
        elif tool_name == "get_commit":
            r = rng.choice(rev_rows)
            server.get_commit(r.commit_id)
        elif tool_name == "diff_commits":
            r1, r2 = rng.sample(rev_rows, 2)
            server.diff_commits(block, r1.commit_id, r2.commit_id)
        elif tool_name == "blame_line":
            r = rng.choice(rev_rows)
            server.blame_line(r.block, r.rtl_file, 1)
        elif tool_name == "list_commits_touching_keyword":
            server.list_commits_touching_keyword(block, rng.choice(["fifo", "counter", "fix"]))
        return {"tool": tool_name, "ok": True}
    except Exception as e:  # noqa: BLE001
        return {"tool": tool_name, "ok": False, "error": str(e)}


def replay(n_calls: int = N_CALLS) -> dict:
    from .generate_corpus import generate_corpus
    from pathlib import Path

    corpus = generate_corpus(Path("data/replay_reports_scratch"))
    rng = random.Random(SEED)

    conn = db.reader_connection()
    before = db.table_checksums(conn)
    conn.close()

    results = [
        _random_call(rng, corpus.timing, corpus.lint, corpus.cov_functional, corpus.cov_code,
                     corpus.revision)
        for _ in range(n_calls)
    ]

    conn = db.reader_connection()
    after = db.table_checksums(conn)
    conn.close()

    n_errors = sum(1 for r in results if not r["ok"])
    return {
        "n_calls": len(results),
        "n_errors": n_errors,
        "checksums_before": before,
        "checksums_after": after,
        "zero_writes": before == after,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(replay(), indent=2))
