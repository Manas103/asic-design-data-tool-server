"""Postgres connection helpers and schema DDL.

Two roles, deliberately: `asic_tools_app` (read-write, used only by the one-time corpus loader,
never by the server) and `asic_tools_reader` (SELECT-only by a Postgres GRANT, used by every
tool in server.py). The read-only property this project's design argument rests on is enforced
at the database layer, not just by "the server's code never calls INSERT/UPDATE/DELETE": see
tests/test_read_only_enforcement.py for a literal attempted write through the reader role.
"""

from __future__ import annotations

import os

import psycopg2
import psycopg2.extensions

APP_DSN = os.environ.get(
    "ASICTOOLS_APP_DSN", "dbname=asic_tools user=asic_tools_app password=asic_tools_app_pw host=localhost"
)
READER_DSN = os.environ.get(
    "ASICTOOLS_READER_DSN",
    "dbname=asic_tools user=asic_tools_reader password=asic_tools_reader_pw host=localhost",
)

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS timing_lines (
    id SERIAL PRIMARY KEY,
    block TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_line INT NOT NULL,
    run_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    arrival_ps NUMERIC NOT NULL,
    required_ps NUMERIC NOT NULL,
    slack_ps NUMERIC NOT NULL,
    path_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lint_lines (
    id SERIAL PRIMARY KEY,
    block TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_line INT NOT NULL,
    finding_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    rule TEXT NOT NULL,
    rtl_file TEXT NOT NULL,
    rtl_line INT NOT NULL,
    message TEXT NOT NULL,
    waived BOOLEAN NOT NULL,
    waiver_reason TEXT
);

CREATE TABLE IF NOT EXISTS coverage_functional_lines (
    id SERIAL PRIMARY KEY,
    block TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_line INT NOT NULL,
    group_name TEXT NOT NULL,
    bin_name TEXT NOT NULL,
    hit_count INT NOT NULL,
    goal INT NOT NULL
);

CREATE TABLE IF NOT EXISTS coverage_code_lines (
    id SERIAL PRIMARY KEY,
    block TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_line INT NOT NULL,
    rtl_file TEXT NOT NULL,
    rtl_line INT NOT NULL,
    hit_count INT NOT NULL
);

CREATE TABLE IF NOT EXISTS revision_lines (
    id SERIAL PRIMARY KEY,
    block TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_line INT NOT NULL,
    commit_id TEXT NOT NULL,
    author TEXT NOT NULL,
    commit_date DATE NOT NULL,
    rtl_file TEXT NOT NULL,
    lines_added INT NOT NULL,
    lines_removed INT NOT NULL,
    message TEXT NOT NULL
);
"""

ALL_TABLES = (
    "timing_lines",
    "lint_lines",
    "coverage_functional_lines",
    "coverage_code_lines",
    "revision_lines",
)


def app_connection():
    return psycopg2.connect(APP_DSN)


def reader_connection():
    conn = psycopg2.connect(READER_DSN)
    conn.set_session(readonly=True)
    return conn


def create_schema() -> None:
    conn = app_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_DDL)
        conn.commit()
    finally:
        conn.close()


def table_checksums(conn) -> dict[str, int]:
    """A cheap, real integrity check: row count + sum of primary key ids per table."""
    out = {}
    with conn.cursor() as cur:
        for t in ALL_TABLES:
            cur.execute(f"SELECT count(*), coalesce(sum(id), 0) FROM {t}")
            count, idsum = cur.fetchone()
            out[t] = (count, int(idsum))
    return out
