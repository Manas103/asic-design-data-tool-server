"""Proves the read-only property structurally, not by trusting that server.py never calls a
write statement: a literal INSERT through the exact connection every tool uses must fail."""

import psycopg2
import pytest

from asictools import db


def test_reader_connection_cannot_insert():
    conn = db.reader_connection()
    try:
        with pytest.raises(psycopg2.Error):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO timing_lines (block, source_file, source_line, run_id, "
                    "endpoint, arrival_ps, required_ps, slack_ps, path_id) "
                    "VALUES ('x','x',1,'x','x',1,1,1,'x')"
                )
    finally:
        conn.rollback()
        conn.close()


def test_reader_connection_cannot_update():
    conn = db.reader_connection()
    try:
        with pytest.raises(psycopg2.Error):
            with conn.cursor() as cur:
                cur.execute("UPDATE timing_lines SET slack_ps = 0")
    finally:
        conn.rollback()
        conn.close()


def test_reader_connection_cannot_delete():
    conn = db.reader_connection()
    try:
        with pytest.raises(psycopg2.Error):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM timing_lines")
    finally:
        conn.rollback()
        conn.close()


def test_reader_role_itself_lacks_insert_grant_independent_of_client_readonly_flag():
    """Connects as asic_tools_reader without db.py's client-side `set_session(readonly=True)`,
    to prove the refusal is a real Postgres GRANT on the role, not only the driver-level flag
    every tool's connection happens to also set."""
    conn = psycopg2.connect(db.READER_DSN)
    try:
        with pytest.raises(psycopg2.Error):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO timing_lines (block, source_file, source_line, run_id, "
                    "endpoint, arrival_ps, required_ps, slack_ps, path_id) "
                    "VALUES ('x','x',1,'x','x',1,1,1,'x')"
                )
    finally:
        conn.rollback()
        conn.close()


def test_reader_connection_can_still_select():
    conn = db.reader_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM timing_lines")
            (count,) = cur.fetchone()
        assert count > 0
    finally:
        conn.close()
