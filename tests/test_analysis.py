"""Tests for the message-history construction logic."""

from ronny.pass_analysis_lm.analysis import _fake_retrieve_history
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart


def test_fake_retrieve_history_structure() -> None:
    history = _fake_retrieve_history("email/gmail", "password123\nuser: me@example.com\n")
    assert len(history) == 2

    response, request = history
    assert isinstance(response, ModelResponse)
    assert isinstance(request, ModelRequest)

    (tool_call,) = response.parts
    assert isinstance(tool_call, ToolCallPart)
    assert tool_call.tool_name == "get_password_entry"

    (tool_return,) = request.parts
    assert isinstance(tool_return, ToolReturnPart)
    assert tool_return.tool_name == "get_password_entry"
    assert "password123" in tool_return.content
    assert tool_call.tool_call_id == tool_return.tool_call_id


def test_fake_retrieve_history_different_ids() -> None:
    h1 = _fake_retrieve_history("a/b", "secret1")
    h2 = _fake_retrieve_history("c/d", "secret2")
    id1 = h1[0].parts[0].tool_call_id  # type: ignore[union-attr]
    id2 = h2[0].parts[0].tool_call_id  # type: ignore[union-attr]
    assert id1 != id2
