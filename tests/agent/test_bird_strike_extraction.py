from agent.nodes.input_parser import extract_entities, normalize_radiotelephony_text


def test_bird_strike_event_type_and_part():
    text = "天府机坪，川航3349报告紧急情况，当前在 12 滑行道滑行，刚刚发生鸟击，怀疑影响左发"
    normalized = normalize_radiotelephony_text(text)
    entities = extract_entities(normalized, scenario_type="bird_strike")
    assert entities.get("event_type") == "确认鸟击"
    assert entities.get("affected_part") == "左发"
    assert entities.get("position") == "滑行道12"
