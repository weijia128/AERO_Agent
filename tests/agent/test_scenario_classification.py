from agent.nodes.input_parser import identify_scenario
from agent.nodes.input_parser import normalize_radiotelephony_text, extract_entities


def test_identify_bird_strike_over_leak():
    text = "当前在12滑行道滑行，刚刚发生（或疑似）鸟击，怀疑有油液泄漏"
    assert identify_scenario(text) == "bird_strike"


def test_identify_oil_spill():
    text = "501机位燃油泄漏，发动机运转中"
    assert identify_scenario(text) == "oil_spill"


def test_identify_default_to_oil():
    text = "机坪有异味，需要检查"
    assert identify_scenario(text) == "oil_spill"


def test_identify_fod():
    text = "跑道发现异物，疑似FOD"
    assert identify_scenario(text) == "fod"


def test_position_normalization_for_taxiway():
    text = "当前在 12 滑行道滑行"
    normalized = normalize_radiotelephony_text(text)
    entities = extract_entities(normalized)
    assert entities.get("position") == "滑行道12"
