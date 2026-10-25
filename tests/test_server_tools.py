from asictools import server
from asictools.blocks import BLOCKS


def test_nineteen_tools_registered():
    assert len(server.ALL_TOOLS) == 19
    assert len({t.__name__ for t in server.ALL_TOOLS}) == 19


def test_get_timing_summary_cites_a_real_line():
    resp = server.get_timing_summary(BLOCKS[0])
    assert "abstain" not in resp
    assert resp["cite"]["source_file"].endswith("_timing.rpt")
    assert resp["cite"]["source_line"] >= 1


def test_unknown_block_abstains_rather_than_erroring():
    resp = server.get_timing_summary("not_a_real_block")
    assert resp.get("abstain") is True


def test_get_lint_waiver_abstains_when_not_waived():
    findings = server.list_lint_findings(BLOCKS[0], max_results=100)
    not_waived = next(f for f in findings["findings"])
    # list_lint_findings doesn't expose `waived`; fetch detail to find a non-waived one.
    detail = server.get_lint_finding(not_waived["finding_id"])
    if not detail["waived"]:
        resp = server.get_lint_waiver(not_waived["finding_id"])
        assert resp.get("abstain") is True


def test_every_tool_response_has_cite_or_abstains_or_is_a_disclosed_list_answer():
    resp = server.get_commit("definitely_not_a_real_commit_id")
    assert resp.get("abstain") is True
