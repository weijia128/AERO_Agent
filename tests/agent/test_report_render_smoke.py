"""Smoke test for report rendering with Jinja templates."""

from agent.nodes import output_generator as og


def _sample_state():
    """Build a minimal but representative state for oil_spill scenario."""
    return {
        "session_id": "demo-001",
        "scenario_type": "oil_spill",
        "incident": {
            "flight_no": "CA1234",
            "position": "501机位",
            "report_time": "2024-06-01T10:20:00",
            "fluid_type": "FUEL",
            "leak_size": "MEDIUM",
            "continuous": True,
            "engine_status": "RUNNING",
            "discovery_method": "巡查",
            "reported_by": "张三",
        },
        "risk_assessment": {
            "level": "R3",
            "score": 65,
            "factors": ["发动机运转", "持续滴漏"],
        },
        "spatial_analysis": {
            "isolated_nodes": ["501机位"],
            "affected_taxiways": ["H3"],
            "affected_runways": [],
        },
        "flight_impact_prediction": {
            "statistics": {"total_affected_flights": 2, "average_delay_minutes": 25},
            "affected_flights": [
                {
                    "callsign": "CA1234",
                    "estimated_delay_minutes": 25,
                    "delay_reason": "滑行受限",
                }
            ],
        },
        "notifications_sent": [
            {"department": "机务", "timestamp": "2024-06-01T10:25:00", "priority": "high"},
            {"department": "消防", "timestamp": "2024-06-01T10:26:00", "priority": "high"},
        ],
        "mandatory_actions_done": {"maintenance_notified": True, "fire_dept_notified": True},
        "actions_taken": [
            {"action": "assess_risk", "timestamp": "2024-06-01T10:22:00", "result": "评估完成"},
            {
                "action": "notify_department",
                "timestamp": "2024-06-01T10:25:00",
                "result": "已通知机务/消防",
            },
        ],
        "retrieved_knowledge": {
            "regulations": [{"title": "机坪油污处置规范", "cleanup_method": "吸附棉+高压冲洗"}]
        },
    }


def test_render_markdown_smoke(monkeypatch):
    """Render markdown via template; LLM is stubbed to keep test deterministic."""
    fake_summary = {
        "event_description": "501机位燃油泄漏，发动机运转，评估为R3风险。",
        "effect_evaluation": "已完成风险评估并通知机务/消防，处置推进中。",
        "improvement_suggestions": "1. 加强滑行道巡检\n2. 完善燃油泄漏演练\n3. 优化现场警戒流程",
    }

    monkeypatch.setattr(
        og,
        "_generate_event_summary_with_llm",
        lambda **kwargs: fake_summary,
    )

    result = og.output_generator_node(_sample_state())
    markdown = result["final_answer"]

    assert markdown
    required_sections = [
        "## 1. 事件基本信息",
        "## 2. 特情初始确认",
        "## 3. 初期风险控制措施",
        "## 4. 协同单位通知记录",
        "## 5. 区域隔离与现场检查",
        "## 6. 清污处置执行情况",
        "## 7. 处置结果确认",
        "## 8. 区域恢复与运行返还",
        "## 9. 运行影响评估",
        "## 10. 事件总结与改进建议",
        "## 11. 签字与存档",
    ]
    for section in required_sections:
        assert section in markdown


def test_notification_time_displayed_correctly(monkeypatch):
    """Test that notification times are correctly displayed in the report."""
    fake_summary = {
        "event_description": "Test event",
        "effect_evaluation": "Test evaluation",
        "improvement_suggestions": "1. Suggestion 1\n2. Suggestion 2\n3. Suggestion 3",
    }

    monkeypatch.setattr(
        og,
        "_generate_event_summary_with_llm",
        lambda **kwargs: fake_summary,
    )

    # Test case: notifications with timestamps
    result = og.output_generator_node(_sample_state())
    markdown = result["final_answer"]

    # Check that notification times are displayed (not "——")
    assert "| 机务 |" in markdown
    assert "| 消防 |" in markdown

    # Extract the coordination units section
    coordination_section = markdown.split("## 4. 协同单位通知记录")[1].split("##")[0]

    # 机务 should show 10:25:00 (not "——")
    assert "10:25:00" in coordination_section or "10:25" in coordination_section

    # 消防 should show 10:26:00 (not "——")
    assert "10:26:00" in coordination_section or "10:26" in coordination_section

    # Test case: bird strike scenario with 塔台 notification
    bird_strike_state = _sample_state()
    bird_strike_state["scenario_type"] = "bird_strike"
    bird_strike_state["incident"] = {
        "flight_no": "3U3349",
        "position": "滑行道02",
        "report_time": "2026-01-13T11:06:40",
        "event_type": "确认鸟击",
        "affected_part": "发动机",
        "current_status": "异常",
        "crew_request": "返航/机务检查",
        "suspend_resources": False,
        "followup_required": False,
    }
    bird_strike_state["risk_assessment"] = {
        "level": "R4",
        "score": 96.24,
        "factors": [],
    }
    bird_strike_state["notifications_sent"] = [
        {"department": "塔台", "timestamp": "2026-01-13T11:06:45", "priority": "immediate"},
        {"department": "消防", "timestamp": "2026-01-13T11:06:50", "priority": "immediate"},
    ]
    bird_strike_state["mandatory_actions_done"] = {
        "atc_notified": True,  # 塔台通知时设置
        "fire_dept_notified": True,
    }

    result = og.output_generator_node(bird_strike_state)
    markdown = result["final_answer"]
    coordination_section = markdown.split("## 4. 协同单位通知记录")[1].split("##")[0]

    # 机务 should be notified via 塔台 and show time
    assert "11:06:45" in coordination_section or "11:06" in coordination_section
    # 消防 should show time
    assert "11:06:50" in coordination_section or "11:06" in coordination_section
