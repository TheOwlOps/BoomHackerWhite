"""Tests for batched (multi) tool calls in one model response."""

from strix.llm.utils import fix_incomplete_tool_call, parse_tool_invocations


TWO_CALLS = """Checking both endpoints now.
<function=browser_action>
<parameter=action>navigate</parameter>
<parameter=url>https://app.example.com/login</parameter>
</function>
<function=list_requests>
<parameter=page_size>10</parameter>
</function>"""


def test_parse_returns_all_batched_calls() -> None:
    invocations = parse_tool_invocations(TWO_CALLS)
    assert invocations is not None
    assert [inv["toolName"] for inv in invocations] == ["browser_action", "list_requests"]
    assert invocations[0]["args"]["url"] == "https://app.example.com/login"
    assert invocations[1]["args"]["page_size"] == "10"


def test_parse_single_call_still_works() -> None:
    content = "<function=think>\n<parameter=thought>plan</parameter>\n</function>"
    invocations = parse_tool_invocations(content)
    assert invocations is not None
    assert len(invocations) == 1
    assert invocations[0]["toolName"] == "think"


def test_fix_incomplete_closes_last_of_several_calls() -> None:
    truncated = TWO_CALLS + "\n<function=think>\n<parameter=thought>partial thou"
    fixed = fix_incomplete_tool_call(truncated)
    invocations = parse_tool_invocations(fixed)
    assert invocations is not None
    assert [inv["toolName"] for inv in invocations] == [
        "browser_action",
        "list_requests",
        "think",
    ]


def test_fix_incomplete_single_call_unchanged_behaviour() -> None:
    truncated = "<function=think>\n<parameter=thought>abc"
    fixed = fix_incomplete_tool_call(truncated)
    invocations = parse_tool_invocations(fixed)
    assert invocations is not None
    assert invocations[0]["args"]["thought"] == "abc"


def test_fix_incomplete_noop_when_all_closed() -> None:
    assert fix_incomplete_tool_call(TWO_CALLS) == TWO_CALLS
