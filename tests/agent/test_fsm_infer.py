from fsm.engine import FSMEngine
from fsm.states import FSMStateEnum


def test_fsm_infer_p1_risk_assess():
    engine = FSMEngine(scenario_type="oil_spill")
    state = {
        "scenario_type": "oil_spill",
        "checklist": {
            "fluid_type": True,
            "position": True,
        },
        "mandatory_actions_done": {},
        "risk_assessment": {},
    }
    assert engine.infer_state(state) == FSMStateEnum.P1_RISK_ASSESS.value
