"""Generates the synthetic design/CAD artifact corpus: one flat text report file per
(block, artifact type) under data/reports/, and the exact same data as structured rows,
line-numbered against the file each row actually came from, so every tool's citation is a real
(file, line) pointing at that line's exact text in a committed sample report.

Fixed seed 20261101. All data is synthetic; stated as such in the README per this portfolio's
honest-framing convention.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from .blocks import BLOCKS

SEED = 20261101
RTL_FILES = ["rtl/{block}_top.sv", "rtl/{block}_fsm.sv", "rtl/{block}_regs.sv", "rtl/{block}_datapath.sv"]
LINT_RULES = [
    "UNUSED_SIGNAL",
    "WIDTH_MISMATCH",
    "LATCH_INFERRED",
    "MULTI_DRIVEN_NET",
    "MISSING_DEFAULT_CASE",
    "COMBO_LOOP_RISK",
]
AUTHORS = ["dv_eng_a", "dv_eng_b", "rtl_eng_a", "rtl_eng_b", "arch_eng_a"]


@dataclass
class TimingRow:
    block: str
    source_file: str
    source_line: int
    run_id: str
    endpoint: str
    arrival_ps: float
    required_ps: float
    slack_ps: float
    path_id: str


@dataclass
class LintRow:
    block: str
    source_file: str
    source_line: int
    finding_id: str
    severity: str
    rule: str
    rtl_file: str
    rtl_line: int
    message: str
    waived: bool
    waiver_reason: str | None


@dataclass
class CovFunctionalRow:
    block: str
    source_file: str
    source_line: int
    group_name: str
    bin_name: str
    hit_count: int
    goal: int


@dataclass
class CovCodeRow:
    block: str
    source_file: str
    source_line: int
    rtl_file: str
    rtl_line: int
    hit_count: int


@dataclass
class RevisionRow:
    block: str
    source_file: str
    source_line: int
    commit_id: str
    author: str
    commit_date: str
    rtl_file: str
    lines_added: int
    lines_removed: int
    message: str


@dataclass
class Corpus:
    timing: list[TimingRow]
    lint: list[LintRow]
    cov_functional: list[CovFunctionalRow]
    cov_code: list[CovCodeRow]
    revision: list[RevisionRow]


def generate_corpus(reports_dir: Path) -> Corpus:
    reports_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    timing_rows: list[TimingRow] = []
    lint_rows: list[LintRow] = []
    cov_f_rows: list[CovFunctionalRow] = []
    cov_c_rows: list[CovCodeRow] = []
    rev_rows: list[RevisionRow] = []

    for block in BLOCKS:
        # --- timing report: two corners (typical and fast), same endpoint set, so
        # compare_timing_runs has a real delta to report ---
        timing_file = f"reports/{block}_timing.rpt"
        lines = [f"# Synthesis timing report for {block}, corners tt_0p80v_125c and ff_0p88v_m40c"]
        n_endpoints = rng.randint(30, 45)
        endpoint_names = [f"{block}_u/reg_{i}/D" for i in range(n_endpoints)]
        for run_id, shift in (("tt_0p80v_125c", 0.0), ("ff_0p88v_m40c", -0.25)):
            for i, endpoint in enumerate(endpoint_names):
                required = round(rng.uniform(800, 1500), 2)
                base_arrival = required - rng.uniform(-50, 400)
                arrival = round(base_arrival * (1 + shift), 2)
                slack = round(required - arrival, 2)
                path_id = f"{block}_path_{i:03d}"
                lines.append(
                    f"ENDPOINT {endpoint} ARRIVAL {arrival} REQUIRED {required} SLACK {slack} "
                    f"PATH {path_id} RUN {run_id}"
                )
        (reports_dir / f"{block}_timing.rpt").write_text("\n".join(lines) + "\n")
        for i, line_text in enumerate(lines[1:], start=2):  # header is line 1
            parts = dict(zip(line_text.split()[0::2], line_text.split()[1::2]))
            timing_rows.append(
                TimingRow(
                    block=block,
                    source_file=timing_file,
                    source_line=i,
                    run_id=parts["RUN"],
                    endpoint=parts["ENDPOINT"],
                    arrival_ps=float(parts["ARRIVAL"]),
                    required_ps=float(parts["REQUIRED"]),
                    slack_ps=float(parts["SLACK"]),
                    path_id=parts["PATH"],
                )
            )

        # --- lint findings ---
        lint_file = f"reports/{block}_lint.log"
        lines = [f"# Lint findings for {block}"]
        n_findings = rng.randint(20, 32)
        for i in range(n_findings):
            severity = rng.choice(["ERROR", "WARNING", "WARNING", "INFO"])
            rule = rng.choice(LINT_RULES)
            rtl_file = rng.choice(RTL_FILES).format(block=block)
            rtl_line = rng.randint(10, 400)
            finding_id = f"{block}_lint_{i:03d}"
            waived = rng.random() < 0.2
            waiver_reason = "false positive, confirmed by design review" if waived else None
            message = f"{rule} at {rtl_file}:{rtl_line}"
            extra = f" WAIVED={waiver_reason}" if waived else ""
            lines.append(
                f"{severity} {finding_id} {rule} {rtl_file}:{rtl_line} {message}{extra}"
            )
            lint_rows.append(
                LintRow(
                    block=block,
                    source_file=lint_file,
                    source_line=i + 2,
                    finding_id=finding_id,
                    severity=severity,
                    rule=rule,
                    rtl_file=rtl_file,
                    rtl_line=rtl_line,
                    message=message,
                    waived=waived,
                    waiver_reason=waiver_reason,
                )
            )
        (reports_dir / f"{block}_lint.log").write_text("\n".join(lines) + "\n")

        # --- coverage report (functional bins, then code lines) ---
        cov_file = f"reports/{block}_coverage.rpt"
        lines = [f"# Coverage report for {block}"]
        n_fgroups = rng.randint(6, 10)
        for i in range(n_fgroups):
            group = f"{block}_cg_{i}"
            n_bins = rng.randint(2, 5)
            for b in range(n_bins):
                bin_name = f"bin_{b}"
                goal = 100
                hit = rng.choice([0, rng.randint(1, 99), 100, 100, 100])
                lines.append(f"FCOV {group}.{bin_name} HITS {hit} GOAL {goal}")
                cov_f_rows.append(
                    CovFunctionalRow(
                        block=block,
                        source_file=cov_file,
                        source_line=len(lines),
                        group_name=group,
                        bin_name=bin_name,
                        hit_count=hit,
                        goal=goal,
                    )
                )
        n_code_lines = rng.randint(15, 25)
        for i in range(n_code_lines):
            rtl_file = rng.choice(RTL_FILES).format(block=block)
            rtl_line = rng.randint(10, 400)
            hit = rng.choice([0, 0, rng.randint(1, 500)])
            lines.append(f"CCOV {rtl_file}:{rtl_line} HITS {hit}")
            cov_c_rows.append(
                CovCodeRow(
                    block=block,
                    source_file=cov_file,
                    source_line=len(lines),
                    rtl_file=rtl_file,
                    rtl_line=rtl_line,
                    hit_count=hit,
                )
            )
        (reports_dir / f"{block}_coverage.rpt").write_text("\n".join(lines) + "\n")

        # --- revision history ---
        rev_file = f"reports/{block}_revision.log"
        lines = [f"# Revision history for {block}"]
        n_commits = rng.randint(20, 30)
        for i in range(n_commits):
            commit_id = f"{block[:4]}{i:04x}"
            author = rng.choice(AUTHORS)
            month = rng.randint(1, 10)
            day = rng.randint(1, 28)
            commit_date = f"2026-{month:02d}-{day:02d}"
            rtl_file = rng.choice(RTL_FILES).format(block=block)
            added = rng.randint(1, 60)
            removed = rng.randint(0, 30)
            message = rng.choice(
                [
                    "fix off-by-one in fifo pointer",
                    "add missing default case",
                    "widen counter to avoid wraparound",
                    "refactor fsm for readability",
                    "add assertion for onehot check",
                    "fix lint warning on unused signal",
                    "update register reset value",
                ]
            )
            lines.append(
                f"COMMIT {commit_id} AUTHOR {author} DATE {commit_date} FILE {rtl_file} "
                f"+{added} -{removed} MSG \"{message}\""
            )
            rev_rows.append(
                RevisionRow(
                    block=block,
                    source_file=rev_file,
                    source_line=len(lines),
                    commit_id=commit_id,
                    author=author,
                    commit_date=commit_date,
                    rtl_file=rtl_file,
                    lines_added=added,
                    lines_removed=removed,
                    message=message,
                )
            )
        (reports_dir / f"{block}_revision.log").write_text("\n".join(lines) + "\n")

    return Corpus(timing_rows, lint_rows, cov_f_rows, cov_c_rows, rev_rows)


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/reports")
    c = generate_corpus(out)
    print(
        f"timing={len(c.timing)} lint={len(c.lint)} cov_functional={len(c.cov_functional)} "
        f"cov_code={len(c.cov_code)} revision={len(c.revision)}"
    )
