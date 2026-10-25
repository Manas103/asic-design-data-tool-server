"""The read-only MCP tool server: 19 typed tools over synthesis timing, lint, coverage and
revision-history artifacts, behind one `mcp.server.mcpserver.MCPServer` instance.

Every tool opens `db.reader_connection()`, never `db.app_connection()`: the reader role has only
SELECT granted at the Postgres level (db.py), and `reader_connection()` additionally sets the
session read-only, so a tool that somehow tried to write would be rejected by Postgres itself,
not merely by the absence of write code (see tests/test_read_only_enforcement.py for a literal
attempted write that this structurally refuses).

Every tool returns either a `cite` field naming the exact (source_file, source_line) the answer
rests on, or `{"abstain": true, "reason": ...}` when nothing in the corpus answers the question.
No tool ever returns a bare answer with no citation and no abstention.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import db

server = MCPServer(name="asic-design-data-tools")
_RO = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)


def _cite(source_file: str, source_line: int) -> dict:
    return {"source_file": source_file, "source_line": source_line}


def _abstain(reason: str) -> dict:
    return {"abstain": True, "reason": reason}


def _query(sql: str, params: tuple) -> list[tuple]:
    conn = db.reader_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


# ---------------- Timing (5) ----------------


@server.tool(annotations=_RO)
def get_timing_summary(block: str, run_id: str = "tt_0p80v_125c") -> dict:
    """Worst (most negative) slack endpoint for a block on a given timing run."""
    rows = _query(
        "SELECT endpoint, slack_ps, source_file, source_line FROM timing_lines "
        "WHERE block=%s AND run_id=%s ORDER BY slack_ps ASC LIMIT 1",
        (block, run_id),
    )
    if not rows:
        return _abstain(f"no timing data for block={block} run_id={run_id}")
    endpoint, slack_ps, sf, sl = rows[0]
    return {"block": block, "run_id": run_id, "worst_endpoint": endpoint,
            "worst_slack_ps": float(slack_ps), "cite": _cite(sf, sl)}


@server.tool(annotations=_RO)
def list_timing_violations(block: str, run_id: str = "tt_0p80v_125c", max_results: int = 20) -> dict:
    """Endpoints with negative slack (timing violations) on a given run."""
    rows = _query(
        "SELECT endpoint, slack_ps, source_file, source_line FROM timing_lines "
        "WHERE block=%s AND run_id=%s AND slack_ps < 0 ORDER BY slack_ps ASC LIMIT %s",
        (block, run_id, max_results),
    )
    if not rows:
        return {"block": block, "run_id": run_id, "violations": [],
                "note": "0 violations found (not an abstention: this is a real negative result)"}
    return {"block": block, "run_id": run_id, "violations": [
        {"endpoint": e, "slack_ps": float(s), "cite": _cite(sf, sl)} for e, s, sf, sl in rows
    ]}


@server.tool(annotations=_RO)
def get_critical_path(block: str, path_id: str) -> dict:
    """Timing detail for one named path id."""
    rows = _query(
        "SELECT endpoint, arrival_ps, required_ps, slack_ps, run_id, source_file, source_line "
        "FROM timing_lines WHERE block=%s AND path_id=%s",
        (block, path_id),
    )
    if not rows:
        return _abstain(f"no path {path_id} found for block={block}")
    return {"block": block, "path_id": path_id, "runs": [
        {"run_id": r, "endpoint": e, "arrival_ps": float(a), "required_ps": float(q),
         "slack_ps": float(s), "cite": _cite(sf, sl)}
        for e, a, q, s, r, sf, sl in rows
    ]}


@server.tool(annotations=_RO)
def get_slack_for_endpoint(block: str, endpoint: str, run_id: str = "tt_0p80v_125c") -> dict:
    """Exact slack for a named endpoint on a given run."""
    rows = _query(
        "SELECT slack_ps, source_file, source_line FROM timing_lines "
        "WHERE block=%s AND endpoint=%s AND run_id=%s",
        (block, endpoint, run_id),
    )
    if not rows:
        return _abstain(f"no endpoint {endpoint} found for block={block} run_id={run_id}")
    slack_ps, sf, sl = rows[0]
    return {"block": block, "endpoint": endpoint, "run_id": run_id,
            "slack_ps": float(slack_ps), "cite": _cite(sf, sl)}


@server.tool(annotations=_RO)
def compare_timing_runs(block: str, run_a: str, run_b: str, endpoint: str) -> dict:
    """Slack delta for one endpoint between two timing corners."""
    rows = _query(
        "SELECT run_id, slack_ps, source_file, source_line FROM timing_lines "
        "WHERE block=%s AND endpoint=%s AND run_id IN (%s,%s)",
        (block, endpoint, run_a, run_b),
    )
    by_run = {r: (float(s), _cite(sf, sl)) for r, s, sf, sl in rows}
    if run_a not in by_run or run_b not in by_run:
        return _abstain(f"endpoint {endpoint} missing data for one of {run_a}/{run_b}")
    return {
        "block": block, "endpoint": endpoint,
        run_a: {"slack_ps": by_run[run_a][0], "cite": by_run[run_a][1]},
        run_b: {"slack_ps": by_run[run_b][0], "cite": by_run[run_b][1]},
        "delta_ps": round(by_run[run_b][0] - by_run[run_a][0], 2),
    }


# ---------------- Lint (4) ----------------


@server.tool(annotations=_RO)
def list_lint_findings(block: str, severity: str | None = None, max_results: int = 20) -> dict:
    """Lint findings for a block, optionally filtered by severity (ERROR/WARNING/INFO)."""
    if severity:
        rows = _query(
            "SELECT finding_id, severity, rule, rtl_file, rtl_line, source_file, source_line "
            "FROM lint_lines WHERE block=%s AND severity=%s LIMIT %s",
            (block, severity, max_results),
        )
    else:
        rows = _query(
            "SELECT finding_id, severity, rule, rtl_file, rtl_line, source_file, source_line "
            "FROM lint_lines WHERE block=%s LIMIT %s",
            (block, max_results),
        )
    if not rows:
        return _abstain(f"no lint findings for block={block} severity={severity}")
    return {"block": block, "findings": [
        {"finding_id": fid, "severity": sev, "rule": rule, "rtl_file": rf, "rtl_line": rl,
         "cite": _cite(sf, sl)}
        for fid, sev, rule, rf, rl, sf, sl in rows
    ]}


@server.tool(annotations=_RO)
def get_lint_finding(finding_id: str) -> dict:
    """Full detail for one lint finding id."""
    rows = _query(
        "SELECT block, severity, rule, rtl_file, rtl_line, message, waived, waiver_reason, "
        "source_file, source_line FROM lint_lines WHERE finding_id=%s",
        (finding_id,),
    )
    if not rows:
        return _abstain(f"no lint finding {finding_id}")
    block, sev, rule, rf, rl, msg, waived, reason, sf, sl = rows[0]
    return {"finding_id": finding_id, "block": block, "severity": sev, "rule": rule,
            "rtl_file": rf, "rtl_line": rl, "message": msg, "waived": waived,
            "waiver_reason": reason, "cite": _cite(sf, sl)}


@server.tool(annotations=_RO)
def lint_summary_by_rule(block: str) -> dict:
    """Count of lint findings per rule for a block (an aggregate answer: cites one
    representative finding per rule, not every contributing row)."""
    rows = _query(
        "SELECT rule, count(*), min(finding_id) FROM lint_lines WHERE block=%s GROUP BY rule",
        (block,),
    )
    if not rows:
        return _abstain(f"no lint findings for block={block}")
    detail = _query(
        "SELECT finding_id, source_file, source_line FROM lint_lines WHERE block=%s",
        (block,),
    )
    rep = {fid: (sf, sl) for fid, sf, sl in detail}
    return {"block": block, "by_rule": [
        {"rule": r, "count": c, "representative_finding_id": rep_id,
         "cite": _cite(*rep[rep_id])}
        for r, c, rep_id in rows
    ]}


@server.tool(annotations=_RO)
def get_lint_waiver(finding_id: str) -> dict:
    """Waiver reason for a finding, or abstains if the finding does not exist or is not waived."""
    rows = _query(
        "SELECT waived, waiver_reason, source_file, source_line FROM lint_lines WHERE finding_id=%s",
        (finding_id,),
    )
    if not rows:
        return _abstain(f"no lint finding {finding_id}")
    waived, reason, sf, sl = rows[0]
    if not waived:
        return _abstain(f"finding {finding_id} exists but is not waived")
    return {"finding_id": finding_id, "waiver_reason": reason, "cite": _cite(sf, sl)}


# ---------------- Coverage (5) ----------------


@server.tool(annotations=_RO)
def get_coverage_summary(block: str) -> dict:
    """Functional coverage hit rate for a block, citing the single worst (lowest-hit) bin."""
    rows = _query(
        "SELECT group_name, bin_name, hit_count, goal, source_file, source_line "
        "FROM coverage_functional_lines WHERE block=%s ORDER BY hit_count ASC LIMIT 1",
        (block,),
    )
    agg = _query(
        "SELECT count(*), sum(CASE WHEN hit_count>=goal THEN 1 ELSE 0 END) "
        "FROM coverage_functional_lines WHERE block=%s",
        (block,),
    )
    if not rows or not agg or agg[0][0] == 0:
        return _abstain(f"no functional coverage data for block={block}")
    total, met = agg[0]
    group, bin_name, hit, goal, sf, sl = rows[0]
    return {"block": block, "bins_total": total, "bins_meeting_goal": met,
            "worst_bin": f"{group}.{bin_name}", "worst_hit_count": hit, "worst_goal": goal,
            "cite": _cite(sf, sl)}


@server.tool(annotations=_RO)
def list_coverage_holes(block: str, metric: str = "functional", max_results: int = 20) -> dict:
    """Coverage holes (hit_count == 0): functional bins or code lines, depending on metric."""
    if metric == "functional":
        rows = _query(
            "SELECT group_name, bin_name, source_file, source_line FROM "
            "coverage_functional_lines WHERE block=%s AND hit_count=0 LIMIT %s",
            (block, max_results),
        )
        holes = [{"bin": f"{g}.{b}", "cite": _cite(sf, sl)} for g, b, sf, sl in rows]
    elif metric == "code":
        rows = _query(
            "SELECT rtl_file, rtl_line, source_file, source_line FROM coverage_code_lines "
            "WHERE block=%s AND hit_count=0 LIMIT %s",
            (block, max_results),
        )
        holes = [{"rtl_file": rf, "rtl_line": rl, "cite": _cite(sf, sl)} for rf, rl, sf, sl in rows]
    else:
        return _abstain(f"unknown metric {metric!r}, expected 'functional' or 'code'")
    if not holes:
        return {"block": block, "metric": metric, "holes": [],
                "note": "0 holes found (not an abstention: this is a real negative result)"}
    return {"block": block, "metric": metric, "holes": holes}


@server.tool(annotations=_RO)
def get_functional_coverage_group(block: str, group_name: str) -> dict:
    """All bins in one named functional coverage group."""
    rows = _query(
        "SELECT bin_name, hit_count, goal, source_file, source_line "
        "FROM coverage_functional_lines WHERE block=%s AND group_name=%s",
        (block, group_name),
    )
    if not rows:
        return _abstain(f"no coverage group {group_name} for block={block}")
    return {"block": block, "group_name": group_name, "bins": [
        {"bin_name": b, "hit_count": h, "goal": g, "cite": _cite(sf, sl)}
        for b, h, g, sf, sl in rows
    ]}


@server.tool(annotations=_RO)
def get_code_coverage_line(block: str, rtl_file: str, rtl_line: int) -> dict:
    """Hit count for one exact RTL file/line."""
    rows = _query(
        "SELECT hit_count, source_file, source_line FROM coverage_code_lines "
        "WHERE block=%s AND rtl_file=%s AND rtl_line=%s",
        (block, rtl_file, rtl_line),
    )
    if not rows:
        return _abstain(f"no code coverage data for {rtl_file}:{rtl_line} in block={block}")
    hit, sf, sl = rows[0]
    return {"block": block, "rtl_file": rtl_file, "rtl_line": rtl_line, "hit_count": hit,
            "cite": _cite(sf, sl)}


@server.tool(annotations=_RO)
def list_coverage_below_goal(block: str, max_results: int = 20) -> dict:
    """Functional coverage bins that have not met their goal (0 < hit_count < goal excluded
    holes already covered by list_coverage_holes; this includes holes too, as "not met")."""
    rows = _query(
        "SELECT group_name, bin_name, hit_count, goal, source_file, source_line "
        "FROM coverage_functional_lines WHERE block=%s AND hit_count < goal LIMIT %s",
        (block, max_results),
    )
    if not rows:
        return {"block": block, "below_goal": [],
                "note": "0 bins below goal (not an abstention: this is a real negative result)"}
    return {"block": block, "below_goal": [
        {"bin": f"{g}.{b}", "hit_count": h, "goal": goal, "cite": _cite(sf, sl)}
        for g, b, h, goal, sf, sl in rows
    ]}


# ---------------- RTL revision history (5) ----------------


@server.tool(annotations=_RO)
def get_file_history(block: str, rtl_file: str, max_results: int = 20) -> dict:
    """Commits touching one RTL file, most recent first."""
    rows = _query(
        "SELECT commit_id, author, commit_date, lines_added, lines_removed, message, "
        "source_file, source_line FROM revision_lines WHERE block=%s AND rtl_file=%s "
        "ORDER BY commit_date DESC LIMIT %s",
        (block, rtl_file, max_results),
    )
    if not rows:
        return _abstain(f"no revision history for {rtl_file} in block={block}")
    return {"block": block, "rtl_file": rtl_file, "commits": [
        {"commit_id": c, "author": a, "date": str(d), "lines_added": la, "lines_removed": lr,
         "message": m, "cite": _cite(sf, sl)}
        for c, a, d, la, lr, m, sf, sl in rows
    ]}


@server.tool(annotations=_RO)
def get_commit(commit_id: str) -> dict:
    """Full detail for one commit id."""
    rows = _query(
        "SELECT block, author, commit_date, rtl_file, lines_added, lines_removed, message, "
        "source_file, source_line FROM revision_lines WHERE commit_id=%s",
        (commit_id,),
    )
    if not rows:
        return _abstain(f"no commit {commit_id}")
    block, a, d, rf, la, lr, m, sf, sl = rows[0]
    return {"commit_id": commit_id, "block": block, "author": a, "date": str(d),
            "rtl_file": rf, "lines_added": la, "lines_removed": lr, "message": m,
            "cite": _cite(sf, sl)}


@server.tool(annotations=_RO)
def diff_commits(block: str, commit_a: str, commit_b: str) -> dict:
    """Side-by-side file/added/removed/message for two commits (a line-count diff, not a
    content diff: this corpus does not carry full file text)."""
    rows = _query(
        "SELECT commit_id, rtl_file, lines_added, lines_removed, message, source_file, "
        "source_line FROM revision_lines WHERE block=%s AND commit_id IN (%s,%s)",
        (block, commit_a, commit_b),
    )
    by_id = {c: (rf, la, lr, m, _cite(sf, sl)) for c, rf, la, lr, m, sf, sl in rows}
    if commit_a not in by_id or commit_b not in by_id:
        return _abstain(f"missing one of commits {commit_a}/{commit_b} for block={block}")
    return {"block": block,
            commit_a: dict(zip(["rtl_file", "lines_added", "lines_removed", "message", "cite"],
                                by_id[commit_a])),
            commit_b: dict(zip(["rtl_file", "lines_added", "lines_removed", "message", "cite"],
                                by_id[commit_b]))}


@server.tool(annotations=_RO)
def blame_line(block: str, rtl_file: str, rtl_line: int) -> dict:
    """Most recent commit touching rtl_file. File-granularity approximation, not true
    per-line blame: this corpus does not carry a line-to-commit map, disclosed in the README."""
    rows = _query(
        "SELECT commit_id, author, commit_date, message, source_file, source_line "
        "FROM revision_lines WHERE block=%s AND rtl_file=%s ORDER BY commit_date DESC LIMIT 1",
        (block, rtl_file),
    )
    if not rows:
        return _abstain(f"no revision history for {rtl_file} in block={block}")
    commit_id, author, date, message, sf, sl = rows[0]
    return {"block": block, "rtl_file": rtl_file, "rtl_line_requested": rtl_line,
            "most_recent_commit": commit_id, "author": author, "date": str(date),
            "message": message, "cite": _cite(sf, sl),
            "note": "file-granularity approximation, not true per-line blame"}


@server.tool(annotations=_RO)
def list_commits_touching_keyword(block: str, keyword: str, max_results: int = 20) -> dict:
    """Commits whose message contains a keyword (substring match, not signal-level tracking:
    this corpus's commit messages are free text, not a structured signal changelist)."""
    rows = _query(
        "SELECT commit_id, author, commit_date, message, source_file, source_line "
        "FROM revision_lines WHERE block=%s AND message ILIKE %s LIMIT %s",
        (block, f"%{keyword}%", max_results),
    )
    if not rows:
        return _abstain(f"no commits mentioning {keyword!r} for block={block}")
    return {"block": block, "keyword": keyword, "commits": [
        {"commit_id": c, "author": a, "date": str(d), "message": m, "cite": _cite(sf, sl)}
        for c, a, d, m, sf, sl in rows
    ]}


ALL_TOOLS = [
    get_timing_summary, list_timing_violations, get_critical_path, get_slack_for_endpoint,
    compare_timing_runs, list_lint_findings, get_lint_finding, lint_summary_by_rule,
    get_lint_waiver, get_coverage_summary, list_coverage_holes, get_functional_coverage_group,
    get_code_coverage_line, list_coverage_below_goal, get_file_history, get_commit,
    diff_commits, blame_line, list_commits_touching_keyword,
]

assert len(ALL_TOOLS) == 19

if __name__ == "__main__":
    server.run()
