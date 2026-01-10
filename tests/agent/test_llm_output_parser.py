import json
import pytest

from agent.nodes.reasoning import StructuredOutputParser, ParseError


def test_structured_output_parser_action_ok():
    payload = {
        "thought": "need info",
        "action": "ask_for_detail",
        "action_input": {"field": "position"},
    }
    text = json.dumps(payload, ensure_ascii=True)
    thought, action, action_input, final_answer = StructuredOutputParser.parse(
        text, allowed_actions={"ask_for_detail"}
    )
    assert thought == "need info"
    assert action == "ask_for_detail"
    assert action_input["field"] == "position"
    assert final_answer is None


def test_structured_output_parser_unknown_action():
    payload = {
        "thought": "do something",
        "action": "unknown_tool",
        "action_input": {},
    }
    text = json.dumps(payload, ensure_ascii=True)
    with pytest.raises(ParseError):
        StructuredOutputParser.parse(text, allowed_actions={"ask_for_detail"})
