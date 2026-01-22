import agent.nodes.input_parser as input_parser
from agent.nodes.fsm_validator import fsm_validator_node
from agent.nodes.input_parser import input_parser_node
from agent.state import create_initial_state
from config.settings import settings
from tools.assessment.assess_risk import AssessRiskTool
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool


def test_oil_spill_flow(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SEMANTIC_UNDERSTANDING", False, raising=False)
    monkeypatch.setattr(
        input_parser,
        "extract_entities",
        lambda *args, **kwargs: {
            "position": "501",
            "fluid_type": "FUEL",
            "engine_status": "RUNNING",
            "continuous": True,
        },
    )
    monkeypatch.setattr(input_parser, "extract_entities_llm", lambda *args, **kwargs: {})

    state = create_initial_state(
        session_id="oil-spill-flow",
        scenario_type="oil_spill",
        initial_message="Stand 501 fuel leak, engine running, continuous leak",
    )

    parsed = input_parser_node(state)
    state.update(parsed)

    assert state["incident"]["position"] == "501"
    assert state["incident"]["fluid_type"] == "FUEL"
    assert state["incident"]["engine_status"] == "RUNNING"
    assert state["incident"]["continuous"] is True

    risk_tool = AssessRiskTool()
    risk_result = risk_tool.execute(state, {})
    state.update(risk_result)

    assert state["risk_assessment"]["level"] in {"R3", "R4"}

    spatial_tool = CalculateImpactZoneTool()
    spatial_result = spatial_tool.execute(state, {})
    state.update(spatial_result)

    assert state["spatial_analysis"]["impact_radius"] >= 1
    assert state["spatial_analysis"]["isolated_nodes"]

    fsm_result = fsm_validator_node(state)
    assert fsm_result["fsm_validation_errors"]
