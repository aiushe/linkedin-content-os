from agent import tools
from agent.mcp_loader import server


def _function(tool):
    return getattr(tool, "fn", tool)


def test_mcp_claim_and_voice_tools_share_harness_gates(synthetic_corpus):
    claims_report = _function(server.check_claims)("I reduced routing time by 31%.")
    voice_report = _function(server.get_voice_report)("A grounded synthetic draft.")
    assert claims_report["verdict"] == "block"
    assert claims_report["unmatched"][0]["span"] == "31%"
    assert voice_report["verdict"] == "pass"


def test_agent_exposes_the_same_mcp_preflight_tools(synthetic_corpus):
    claim_report = tools.check_claims_read("I reduced routing time by 31%.")
    voice_report = tools.get_voice_report_read("A grounded synthetic draft.")

    assert claim_report["verdict"] == "block"
    assert voice_report["verdict"] == "pass"
    assert {item.name for item in tools.get_read_tools()} >= {"check_claims", "get_voice_report"}
    assert "log_story" in tools.CLAUDE_CODE_ONLY_MCP_TOOLS
