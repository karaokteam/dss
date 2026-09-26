"""Tool kaydı — iskelette hazır."""

from agent.chat import tools


def test_tools_are_discovered():
    names = {s["function"]["name"] for s in tools.schemas()}
    assert {"assess_image", "scan_all", "list_images", "get_track", "find_reports"} <= names


def test_unknown_tool_returns_error():
    assert "error" in tools.dispatch("yok_boyle_tool", {})
