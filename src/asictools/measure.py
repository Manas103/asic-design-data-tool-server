"""Orchestrates the full measurement run and writes docs/*.

Usage: PYTHONPATH=src python -m asictools.measure docs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .grade import grade_all
from .replay_calls import replay


def main(docs_dir: Path) -> dict:
    docs_dir.mkdir(parents=True, exist_ok=True)

    grading = grade_all()
    per_question = grading.pop("per_question")

    replay_result = replay()
    checksums_before = replay_result.pop("checksums_before")
    checksums_after = replay_result.pop("checksums_after")

    report = {
        "n_tools": 19,
        "qa": grading,
        "replay": replay_result,
    }

    (docs_dir / "measure_report.json").write_text(json.dumps(report, indent=2))
    (docs_dir / "qa_per_question.json").write_text(json.dumps(per_question, indent=2))
    (docs_dir / "replay_checksums.json").write_text(
        json.dumps({"before": checksums_before, "after": checksums_after}, indent=2)
    )

    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    docs = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs")
    main(docs)
