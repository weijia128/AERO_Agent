# -*- coding: utf-8 -*-
"""
Interaction-style extraction tests using oil_spill_test_samples.json.
"""
import json
import os
import re

import pytest

from agent.nodes.input_parser import input_parser_node
from agent.state import FSMState
from config.settings import settings


SAMPLE_FIELDS = {"fluid_type", "continuous", "engine_status", "leak_size", "position"}


def _load_samples() -> list[dict]:
    with open("oil_spill_test_samples.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_samples", [])


SAMPLES = _load_samples()


def _normalize_position(value: str | None) -> str | None:
    if not value:
        return value
    normalized = value.strip()
    normalized = re.sub(
        r"^(?:跑道|RWY|RUNWAY|滑行道|TWY|机位|停机位)\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized.strip()


@pytest.fixture(autouse=True)
def _require_llm():
    if os.environ.get("RUN_LLM_TESTS") != "1":
        pytest.skip("set RUN_LLM_TESTS=1 to run LLM extraction tests")
    if not settings.LLM_API_KEY:
        pytest.skip("LLM_API_KEY is required for LLM extraction tests")


@pytest.mark.parametrize(
    "sample",
    SAMPLES,
    ids=[f"sample_{sample.get('id', idx + 1)}" for idx, sample in enumerate(SAMPLES)],
)
def test_oil_spill_interaction_extraction(sample: dict):
    state = {
        "messages": [{"role": "user", "content": sample["input_text"]}],
        "incident": {},
        "checklist": {},
        "scenario_type": "",
        "fsm_state": FSMState.INIT.value,
        "reasoning_steps": [],
        "iteration_count": 1,
    }

    result = input_parser_node(state)
    assert result["scenario_type"] == "oil_spill"

    incident = result.get("incident", {})
    expected = sample.get("key_factors", {})
    for key in SAMPLE_FIELDS:
        if key not in expected:
            continue
        actual = incident.get(key)
        assert actual is not None, f"{key} should be extracted"
        if key == "position":
            assert _normalize_position(actual) == _normalize_position(expected[key])
        else:
            assert actual == expected[key]
