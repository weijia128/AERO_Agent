from agent.state import create_initial_state
from tools.assessment.assess_bird_strike_risk import AssessBirdStrikeRiskTool


def test_bird_strike_flow():
    state = create_initial_state(
        session_id="bird-strike-flow",
        scenario_type="bird_strike",
        initial_message="suspected bird strike during takeoff roll",
    )
    state["incident"].update(
        {
            "phase": "TAKEOFF_ROLL",
            "affected_part": "ENGINE",
            "evidence": "SYSTEM_WARNING",
            "bird_info": "FLOCK",
            "ops_impact": "BLOCKING_RUNWAY_OR_TAXIWAY",
        }
    )

    tool = AssessBirdStrikeRiskTool()
    result = tool.execute(state, {})

    assert result["risk_assessment"]["level"] in {"R1", "R2", "R3", "R4"}
    assert result["risk_assessment"]["inputs"]["impact_area"] in {"ENGINE", "UNKNOWN"}
    assert result["mandatory_actions_done"]["risk_assessed"] is True
