import pytest

from agent.nodes import input_parser


def _reset_radiotelephony_rules():
    input_parser._RADIOTELEPHONY_RULES = None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("501机位发现燃油泄漏", "501"),
        ("滑行道 19 有油污", "滑行道19"),
        ("跑道01L发现不明油液", "跑道01L"),
        ("跑道 2 有情况", "跑道2"),
        ("234", "234"),
    ],
)
def test_extract_entities_position(text, expected):
    entities = input_parser.extract_entities(text)
    assert entities.get("position") == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("发现液压油泄漏", "HYDRAULIC"),
        ("滑油渗漏", "OIL"),
        ("燃油泄漏", "FUEL"),
    ],
)
def test_extract_entities_fluid_type(text, expected):
    entities = input_parser.extract_entities(text)
    assert entities.get("fluid_type") == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("发动机未关闭", "RUNNING"),
        ("发动机已关闭", "STOPPED"),
        ("发动机还在转", "RUNNING"),
    ],
)
def test_extract_entities_engine_status(text, expected):
    entities = input_parser.extract_entities(text)
    assert entities.get("engine_status") == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("持续滴漏", True),
        ("已经不漏了", False),
    ],
)
def test_extract_entities_continuous(text, expected):
    entities = input_parser.extract_entities(text)
    assert entities.get("continuous") == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("大面积泄漏", "LARGE"),
        ("中等规模渗漏", "MEDIUM"),
        ("情况不清楚", "UNKNOWN"),
    ],
)
def test_extract_entities_leak_size(text, expected):
    entities = input_parser.extract_entities(text)
    assert entities.get("leak_size") == expected


def test_extract_entities_flight_no():
    entities = input_parser.extract_entities("航班CA1234在32号机位")
    assert entities.get("flight_no") == "CA1234"
    assert entities.get("flight_no_display") == "CA1234"


def test_normalize_radiotelephony_text():
    _reset_radiotelephony_rules()
    normalized = input_parser.normalize_radiotelephony_text("阿尔法 幺 拐")
    assert normalized == "A17"
