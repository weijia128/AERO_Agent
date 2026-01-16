from tools.assessment.assess_fod_risk import AssessFodRiskTool


def test_assess_fod_risk_high():
    tool = AssessFodRiskTool()
    state = {
        "incident": {
            "location_area": "RUNWAY",
            "position": "01L",
            "fod_type": "METAL",
            "presence": "ON_SURFACE",
            "report_time": "2024-06-01T10:00:00+08:00",
            "fod_size": "LARGE",
        }
    }

    result = tool.execute(state, {})

    assert result["risk_assessment"]["level"] == "R4"
    assert result["risk_assessment"]["score"] >= 85
    assert result["mandatory_actions_done"]["risk_assessed"] is True


def test_assess_fod_risk_removed_downgrade():
    tool = AssessFodRiskTool()
    state = {
        "incident": {
            "location_area": "RUNWAY",
            "position": "01L",
            "fod_type": "METAL",
            "presence": "REMOVED",
            "report_time": "2024-06-01T10:00:00+08:00",
            "fod_size": "LARGE",
        }
    }

    result = tool.execute(state, {})

    assert result["risk_assessment"]["level"] in {"R2", "R3"}
    assert result["risk_assessment"]["score"] < 85


def test_assess_fod_risk_missing_required():
    tool = AssessFodRiskTool()
    state = {
        "incident": {
            "location_area": "RUNWAY",
            "position": "01L",
        }
    }

    result = tool.execute(state, {})

    assert "risk_assessment" not in result
