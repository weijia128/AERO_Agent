"""
融合方案测试用例
"""
import pytest
from datetime import datetime

from agent.state import create_initial_state, FSMState
from agent.nodes.input_parser import input_parser_node, extract_entities, identify_scenario
from agent.nodes.fsm_validator import (
    determine_fsm_state,
    check_mandatory_actions,
    fsm_validator_node,
)
from tools.assessment.assess_risk import AssessRiskTool
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool


class TestInputParser:
    """输入解析测试"""
    
    def test_extract_entities_basic(self):
        """测试基本实体提取"""
        text = "501机位有飞机漏燃油，发动机还在转"
        entities = extract_entities(text)
        
        assert entities.get("position") == "501"
        assert entities.get("fluid_type") == "FUEL"
        assert entities.get("engine_status") == "RUNNING"
    
    def test_extract_entities_hydraulic(self):
        """测试液压油识别"""
        text = "滑行道A3有液压油泄漏"
        entities = extract_entities(text)
        
        assert entities.get("fluid_type") == "HYDRAULIC"
    
    def test_identify_scenario(self):
        """测试场景识别"""
        assert identify_scenario("飞机漏油") == "oil_spill"
        assert identify_scenario("发生鸟击") == "bird_strike"
        assert identify_scenario("轮胎爆了") == "tire_burst"
    
    def test_input_parser_node(self):
        """测试输入解析节点"""
        state = create_initial_state(
            session_id="test-001",
            initial_message="501机位燃油泄漏，发动机运转中"
        )
        
        result = input_parser_node(state)
        
        assert result["scenario_type"] == "oil_spill"
        assert result["incident"]["position"] == "501"
        assert result["incident"]["fluid_type"] == "FUEL"
        assert result["checklist"]["fluid_type"] == True
        assert result["checklist"]["position"] == True


class TestRiskAssessment:
    """风险评估测试"""
    
    def test_high_risk_fuel_engine_running(self):
        """测试燃油+发动机运转=高危"""
        tool = AssessRiskTool()
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "engine_status": "RUNNING",
            }
        }
        
        result = tool.execute(state, {})
        
        assert result["risk_assessment"]["level"] == "R4"
        assert result["risk_assessment"]["score"] >= 90
        assert result["mandatory_actions_done"]["risk_assessed"] == True
    
    def test_medium_risk_fuel_only(self):
        """测试单纯燃油=中危"""
        tool = AssessRiskTool()
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "engine_status": "STOPPED",
                "continuous": False,
            }
        }
        
        result = tool.execute(state, {})
        
        assert result["risk_assessment"]["level"] == "R3"
    
    def test_low_risk_hydraulic(self):
        """测试液压油=低危"""
        tool = AssessRiskTool()
        state = {
            "incident": {
                "fluid_type": "HYDRAULIC",
                "continuous": False,
            }
        }
        
        result = tool.execute(state, {})
        
        assert result["risk_assessment"]["level"] == "R2"


class TestFSMValidator:
    """FSM 验证测试"""
    
    def test_determine_state_init(self):
        """测试初始状态判定"""
        state = create_initial_state(session_id="test")
        
        fsm_state = determine_fsm_state(state)
        
        assert fsm_state == FSMState.INIT
    
    def test_determine_state_risk_assess(self):
        """测试风险评估状态判定"""
        state = create_initial_state(session_id="test")
        state["checklist"]["fluid_type"] = True
        state["checklist"]["position"] = True
        
        fsm_state = determine_fsm_state(state)
        
        assert fsm_state == FSMState.P1_RISK_ASSESS
    
    def test_check_mandatory_actions_high_risk(self):
        """测试高危强制动作检查"""
        state = create_initial_state(session_id="test")
        state["risk_assessment"] = {"level": "R3"}
        state["mandatory_actions_done"]["fire_dept_notified"] = False
        
        errors = check_mandatory_actions(state)
        
        assert len(errors) > 0
        assert "消防" in errors[0]
    
    def test_check_mandatory_actions_fire_notified(self):
        """测试消防已通知无错误"""
        state = create_initial_state(session_id="test")
        state["risk_assessment"] = {"level": "R3"}
        state["mandatory_actions_done"]["fire_dept_notified"] = True
        
        errors = check_mandatory_actions(state)
        
        # 只检查消防相关错误
        fire_errors = [e for e in errors if "消防" in e]
        assert len(fire_errors) == 0


class TestSpatialAnalysis:
    """空间分析测试"""
    
    def test_calculate_impact_zone_high_risk(self):
        """测试高危影响范围计算"""
        tool = CalculateImpactZoneTool()
        state = {
            "incident": {"position": "机位0", "fluid_type": "FUEL"},
            "risk_assessment": {"level": "R4"},
        }

        result = tool.execute(state, {"risk_level": "R4"})

        spatial = result["spatial_analysis"]
        assert "corrected_stand_0" in spatial["isolated_nodes"]
        assert len(spatial["isolated_nodes"]) > 1  # 应该有扩散
        assert spatial["impact_radius"] == 3
    
    def test_calculate_impact_zone_low_risk(self):
        """测试低危影响范围计算"""
        tool = CalculateImpactZoneTool()
        state = {
            "incident": {"position": "机位0", "fluid_type": "HYDRAULIC"},
            "risk_assessment": {"level": "R1"},
        }

        result = tool.execute(state, {"risk_level": "R1"})

        spatial = result["spatial_analysis"]
        assert spatial["impact_radius"] <= 1


class TestIntegration:
    """集成测试"""
    
    def test_full_workflow_simulation(self):
        """模拟完整工作流"""
        # 1. 创建初始状态
        state = create_initial_state(
            session_id="integration-test",
            initial_message="501机位CA123航班燃油泄漏，发动机还在转，面积大约2平米"
        )
        
        # 2. 输入解析
        result = input_parser_node(state)
        state.update(result)
        
        # 验证解析结果
        assert state["incident"]["position"] == "501"
        assert state["incident"]["fluid_type"] == "FUEL"
        assert state["incident"]["engine_status"] == "RUNNING"
        
        # 3. 风险评估
        risk_tool = AssessRiskTool()
        risk_result = risk_tool.execute(state, {})
        state["risk_assessment"] = risk_result["risk_assessment"]
        state["mandatory_actions_done"].update(risk_result.get("mandatory_actions_done", {}))
        
        # 验证风险评估
        assert state["risk_assessment"]["level"] == "R4"
        
        # 4. FSM 验证
        fsm_result = fsm_validator_node(state)
        state.update(fsm_result)
        
        # 验证 FSM 状态
        # 由于未通知消防，应该有验证错误
        assert len(state.get("fsm_validation_errors", [])) > 0
        
        # 5. 模拟通知消防
        state["mandatory_actions_done"]["fire_dept_notified"] = True
        
        # 6. 再次 FSM 验证
        fsm_result = fsm_validator_node(state)
        state.update(fsm_result)
        
        # 消防错误应该消失
        fire_errors = [e for e in state.get("fsm_validation_errors", []) if "消防" in e]
        assert len(fire_errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
