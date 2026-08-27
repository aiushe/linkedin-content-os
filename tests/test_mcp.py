from agent.mcp_loader import server


def _function(tool):
    return getattr(tool, "fn", tool)


def test_mcp_claim_and_voice_tools_share_harness_gates(synthetic_corpus):
    claims_report = _function(server.check_claims)("I reduced routing time by 31%.")
    voice_report = _function(server.get_voice_report)("A grounded synthetic draft.")
    assert claims_report["verdict"] == "block"
    assert claims_report["unmatched"][0]["span"] == "31%"
    assert voice_report["verdict"] == "pass"
