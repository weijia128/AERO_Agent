"""
交叉验证风险评估工具测试
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from tools.assessment.cross_validate_assessment import CrossValidateRiskTool
from config.validation_config import ValidationConfig


class TestCrossValidateRiskTool:
    """交叉验证风险评估工具测试类"""

    def setup_method(self):
        """测试前准备"""
        self.tool = CrossValidateRiskTool()

        # 保存原始配置
        self.original_enable_validation = ValidationConfig.ENABLE_CROSS_VALIDATION
        self.original_validate_risk = ValidationConfig.VALIDATE_RISK_ASSESSMENT
        self.original_sampling_rate = ValidationConfig.SAMPLING_RATE

        # 确保测试时启用验证
        ValidationConfig.ENABLE_CROSS_VALIDATION = True
        ValidationConfig.VALIDATE_RISK_ASSESSMENT = True
        ValidationConfig.SAMPLING_RATE = 1.0  # 100% 采样

    def teardown_method(self):
        """测试后清理"""
        # 恢复原始配置
        ValidationConfig.ENABLE_CROSS_VALIDATION = self.original_enable_validation
        ValidationConfig.VALIDATE_RISK_ASSESSMENT = self.original_validate_risk
        ValidationConfig.SAMPLING_RATE = self.original_sampling_rate

    def test_validation_disabled(self):
        """测试交叉验证禁用时回退到规则引擎"""
        ValidationConfig.ENABLE_CROSS_VALIDATION = False

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE",
                "continuous": True,
                "engine_status": "RUNNING"
            }
        }

        result = self.tool.execute(state, {})

        # 应该回退到纯规则引擎
        assert "risk_assessment" in result
        assert result["risk_assessment"]["level"] == "R4"
        assert "validation_report" not in result  # 不应该有验证报告

    @patch.object(CrossValidateRiskTool, '_llm_validate_risk')
    def test_consistent_validation(self, mock_llm_validate):
        """测试一致性验证（规则 = LLM）"""
        # Mock LLM 返回一致的结果
        mock_llm_validate.return_value = {
            "level": "R4",
            "confidence": 0.9,
            "reasoning": "燃油 + 大面积 + 发动机运转 = 极高风险"
        }

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE",
                "continuous": True,
                "engine_status": "RUNNING"
            }
        }

        result = self.tool.execute(state, {})

        # 验证最终结果
        assert result["risk_assessment"]["level"] == "R4"

        # 验证报告
        validation_report = result["validation_report"]
        assert validation_report["consistency"]["is_consistent"] is True
        assert validation_report["final_decision"]["level"] == "R4"
        assert validation_report["needs_manual_review"] is False

    @patch.object(CrossValidateRiskTool, '_llm_validate_risk')
    def test_conflict_low_confidence(self, mock_llm_validate):
        """测试冲突但 LLM 置信度过低（忽略 LLM）"""
        # Mock LLM 返回不一致但低置信度的结果
        mock_llm_validate.return_value = {
            "level": "R2",  # 规则是 R4，LLM 是 R2
            "confidence": 0.6,  # 低于阈值 0.75
            "reasoning": "可能不严重"
        }

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE",
                "continuous": True,
                "engine_status": "RUNNING"
            }
        }

        result = self.tool.execute(state, {})

        # 应该保留规则引擎结果
        assert result["risk_assessment"]["level"] == "R4"

        # 验证报告
        validation_report = result["validation_report"]
        assert validation_report["consistency"]["is_consistent"] is True  # 因为置信度过低被忽略
        assert "置信度过低" in validation_report["consistency"]["conflict_details"]

    @patch.object(CrossValidateRiskTool, '_llm_validate_risk')
    def test_conflict_high_confidence_small_diff(self, mock_llm_validate):
        """测试冲突 + 高置信度 + 小差异（1级）"""
        # Mock LLM 返回不一致但高置信度的结果（差1级）
        mock_llm_validate.return_value = {
            "level": "R3",  # 规则是 R4，LLM 是 R3，差1级
            "confidence": 0.9,
            "reasoning": "风险较高但不至于 R4"
        }

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE",
                "continuous": True,
                "engine_status": "RUNNING"
            }
        }

        result = self.tool.execute(state, {})

        # 应该采用更严格的评级（R4）
        assert result["risk_assessment"]["level"] == "R4"

        # 验证报告
        validation_report = result["validation_report"]
        assert validation_report["consistency"]["is_consistent"] is False
        assert validation_report["final_decision"]["level"] == "R4"
        assert "更严格评级" in validation_report["final_decision"]["resolution_strategy"]

    @patch.object(CrossValidateRiskTool, '_llm_validate_risk')
    def test_conflict_high_confidence_large_diff(self, mock_llm_validate):
        """测试冲突 + 高置信度 + 大差异（>=2级）"""
        # Mock LLM 返回不一致但高置信度的结果（差2级）
        mock_llm_validate.return_value = {
            "level": "R2",  # 规则是 R4，LLM 是 R2，差2级
            "confidence": 0.9,
            "reasoning": "我认为是中等风险"
        }

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE",
                "continuous": True,
                "engine_status": "RUNNING"
            }
        }

        result = self.tool.execute(state, {})

        # 应该采用更严格的评级（R4）
        assert result["risk_assessment"]["level"] == "R4"

        # 验证报告
        validation_report = result["validation_report"]
        assert validation_report["consistency"]["is_consistent"] is False
        assert validation_report["final_decision"]["level"] == "R4"
        assert validation_report["needs_manual_review"] is True  # 差异过大，需要人工复核

    @patch.object(CrossValidateRiskTool, '_llm_validate_risk')
    def test_llm_stricter_than_rule(self, mock_llm_validate):
        """测试 LLM 更严格的情况"""
        # Mock LLM 返回更严格的评级
        mock_llm_validate.return_value = {
            "level": "R3",  # LLM 是 R3，规则是 R2
            "confidence": 0.9,
            "reasoning": "考虑到其他因素，风险更高"
        }

        state = {
            "incident": {
                "fluid_type": "HYDRAULIC",
                "leak_size": "SMALL"
            }
        }

        result = self.tool.execute(state, {})

        # 应该采用更严格的评级（R3）
        assert result["risk_assessment"]["level"] == "R3"

        # 验证报告
        validation_report = result["validation_report"]
        assert validation_report["consistency"]["is_consistent"] is False
        assert validation_report["final_decision"]["level"] == "R3"

    @patch.object(CrossValidateRiskTool, '_llm_validate_risk')
    def test_llm_validation_failure(self, mock_llm_validate):
        """测试 LLM 验证失败时的回退"""
        # Mock LLM 抛出异常
        mock_llm_validate.side_effect = Exception("LLM 调用失败")

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE"
            }
        }

        # 不应该抛出异常，应该回退到规则引擎结果
        result = self.tool.execute(state, {})

        assert "risk_assessment" in result
        assert result["risk_assessment"]["level"] in ["R1", "R2", "R3", "R4"]

    def test_calculate_level_difference(self):
        """测试风险等级差异计算"""
        # 测试各种差异
        assert self.tool._calculate_level_difference("R1", "R1") == 0
        assert self.tool._calculate_level_difference("R1", "R2") == 1
        assert self.tool._calculate_level_difference("R1", "R4") == 3
        assert self.tool._calculate_level_difference("R4", "R1") == 3
        assert self.tool._calculate_level_difference("R2", "R3") == 1

    def test_get_stricter_level(self):
        """测试获取更严格的等级"""
        # 测试各种组合
        assert self.tool._get_stricter_level("R1", "R2") == "R2"
        assert self.tool._get_stricter_level("R4", "R2") == "R4"
        assert self.tool._get_stricter_level("R3", "R3") == "R3"
        assert self.tool._get_stricter_level("R2", "R4") == "R4"

    @patch.object(CrossValidateRiskTool, '_llm_validate_risk')
    def test_sampling_rate_control(self, mock_llm_validate):
        """测试采样率控制"""
        # 设置采样率为 0（不应该调用 LLM）
        ValidationConfig.SAMPLING_RATE = 0.0

        # Mock LLM（但不应该被调用）
        mock_llm_validate.return_value = {
            "level": "R3",
            "confidence": 0.9,
            "reasoning": "测试"
        }

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE"
            }
        }

        result = self.tool.execute(state, {})

        # LLM 不应该被调用
        mock_llm_validate.assert_not_called()

        # 应该回退到规则引擎
        assert "risk_assessment" in result
        assert "validation_report" not in result


class TestValidationIntegration:
    """集成测试：真实调用（需要 LLM API Key）"""

    @pytest.mark.skip(reason="需要真实 LLM API Key，跳过集成测试")
    def test_real_llm_validation(self):
        """真实 LLM 验证测试（手动运行）"""
        tool = CrossValidateRiskTool()

        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE",
                "continuous": True,
                "engine_status": "RUNNING"
            }
        }

        result = tool.execute(state, {})

        # 检查返回结构
        assert "risk_assessment" in result
        assert "validation_report" in result

        # 打印验证报告
        import json
        print(json.dumps(result["validation_report"], ensure_ascii=False, indent=2))
