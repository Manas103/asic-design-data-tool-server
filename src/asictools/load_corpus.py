"""One-time ETL: generates the corpus and loads it into Postgres via the read-write app role.

This is the only code in this repo that ever writes to these tables. server.py's tools never
call this module and never hold a connection capable of writing (see db.py, reader_connection).
"""

from __future__ import annotations

from pathlib import Path

from . import db
from .generate_corpus import generate_corpus


def load(reports_dir: Path) -> None:
    corpus = generate_corpus(reports_dir)
    db.create_schema()
    conn = db.app_connection()
    try:
        with conn.cursor() as cur:
            for t in db.ALL_TABLES:
                cur.execute(f"TRUNCATE {t} RESTART IDENTITY")
            for r in corpus.timing:
                cur.execute(
                    "INSERT INTO timing_lines (block, source_file, source_line, run_id, "
                    "endpoint, arrival_ps, required_ps, slack_ps, path_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (r.block, r.source_file, r.source_line, r.run_id, r.endpoint, r.arrival_ps,
                     r.required_ps, r.slack_ps, r.path_id),
                )
            for r in corpus.lint:
                cur.execute(
                    "INSERT INTO lint_lines (block, source_file, source_line, finding_id, "
                    "severity, rule, rtl_file, rtl_line, message, waived, waiver_reason) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (r.block, r.source_file, r.source_line, r.finding_id, r.severity, r.rule,
                     r.rtl_file, r.rtl_line, r.message, r.waived, r.waiver_reason),
                )
            for r in corpus.cov_functional:
                cur.execute(
                    "INSERT INTO coverage_functional_lines (block, source_file, source_line, "
                    "group_name, bin_name, hit_count, goal) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (r.block, r.source_file, r.source_line, r.group_name, r.bin_name,
                     r.hit_count, r.goal),
                )
            for r in corpus.cov_code:
                cur.execute(
                    "INSERT INTO coverage_code_lines (block, source_file, source_line, "
                    "rtl_file, rtl_line, hit_count) VALUES (%s,%s,%s,%s,%s,%s)",
                    (r.block, r.source_file, r.source_line, r.rtl_file, r.rtl_line, r.hit_count),
                )
            for r in corpus.revision:
                cur.execute(
                    "INSERT INTO revision_lines (block, source_file, source_line, commit_id, "
                    "author, commit_date, rtl_file, lines_added, lines_removed, message) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (r.block, r.source_file, r.source_line, r.commit_id, r.author,
                     r.commit_date, r.rtl_file, r.lines_added, r.lines_removed, r.message),
                )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/reports")
    load(out)
    print("loaded corpus into Postgres")
