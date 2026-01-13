"""
测试 RadiotelephonyNormalizer 工具
"""
import pytest
from tools.information.radiotelephony_normalizer import (
    RadiotelephonyNormalizerTool,
    RadiotelephonyNormalizer
)


class TestRadiotelephonyNormalizer:
    """测试航空读法规范化工具"""

    def setup_method(self):
        """每个测试前初始化"""
        self.tool = RadiotelephonyNormalizerTool()
        self.normalizer = RadiotelephonyNormalizer()

    # ========== 跑道格式测试 ==========

    def test_normalize_runway_format_02L(self):
        """测试跑道格式规范化: 02L"""
        result = self.tool.execute({}, {"text": "跑道洞两左"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("position") == "02L"
        assert result["confidence"] > 0.7

    def test_normalize_runway_format_18R(self):
        """测试跑道格式规范化: 18R"""
        result = self.tool.execute({}, {"text": "跑道幺八右"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("position") == "18R"
        assert result["confidence"] > 0.7

    def test_normalize_runway_format_09C(self):
        """测试跑道格式规范化: 09C"""
        result = self.tool.execute({}, {"text": "跑道洞九中"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("position") == "09C"
        assert result["confidence"] > 0.7

    # ========== 机位格式测试 ==========

    def test_normalize_stand_format_501(self):
        """测试机位格式规范化: 501"""
        result = self.tool.execute({}, {"text": "五洞幺机位"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("position") == "501"
        assert result["confidence"] > 0.7

    def test_normalize_stand_format_32(self):
        """测试机位格式规范化: 32"""
        result = self.tool.execute({}, {"text": "三两号机位"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("position") == "32"
        assert result["confidence"] > 0.7

    def test_normalize_stand_format_234(self):
        """测试机位格式规范化: 234"""
        result = self.tool.execute({}, {"text": "两三四停机位"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("position") == "234"
        assert result["confidence"] > 0.7

    # ========== 航班号格式测试 ==========

    def test_normalize_flight_number_3U3177(self):
        """测试航班号格式规范化: 3U3177"""
        result = self.tool.execute({}, {"text": "川航三幺拐拐"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("flight_no") == "3U3177"
        assert result["confidence"] > 0.7

    def test_normalize_flight_number_CA1234(self):
        """测试航班号格式规范化: CA1234"""
        result = self.tool.execute({}, {"text": "国航幺两三四"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("flight_no") == "CA1234"
        assert result["confidence"] > 0.7

    def test_normalize_flight_number_MU8567(self):
        """测试航班号格式规范化: MU8567"""
        result = self.tool.execute({}, {"text": "东航八五六拐"})

        assert result["normalized_text"] is not None
        assert result["entities"].get("flight_no") == "MU8567"
        assert result["confidence"] > 0.7

    # ========== 复杂场景测试 ==========

    def test_normalize_complex_oil_spill(self):
        """测试复杂输入规范化: 漏油场景"""
        text = "川航三幺拐拐 五洞幺机位 报告燃油泄漏"
        result = self.tool.execute({}, {"text": text})

        assert result["normalized_text"] is not None
        entities = result["entities"]

        # 验证提取的实体
        assert entities.get("flight_no") == "3U3177"
        assert entities.get("position") == "501"
        assert entities.get("fluid_type") in ["FUEL", None]  # LLM可能提取或不提取
        assert result["confidence"] > 0.7

    def test_normalize_complex_bird_strike(self):
        """测试复杂输入规范化: 鸟击场景"""
        text = "跑道洞两左 疑似鸟击"
        result = self.tool.execute({}, {"text": text})

        assert result["normalized_text"] is not None
        entities = result["entities"]

        # 验证提取的实体
        assert entities.get("position") == "02L"
        assert result["confidence"] > 0.7

    def test_normalize_complex_hydraulic_leak(self):
        """测试复杂输入规范化: 液压油泄漏场景"""
        text = "滑行道A三 液压油泄漏 发动机关闭"
        result = self.tool.execute({}, {"text": text})

        assert result["normalized_text"] is not None
        entities = result["entities"]

        # 验证提取的实体
        assert entities.get("position") == "A3"
        assert result["confidence"] > 0.7

    # ========== 边界情况测试 ==========

    def test_normalize_empty_text(self):
        """测试空文本"""
        result = self.tool.execute({}, {"text": ""})

        assert result["normalized_text"] == ""
        assert result["entities"] == {}
        assert result["confidence"] == 0.0

    def test_normalize_no_aviation_content(self):
        """测试非航空内容"""
        result = self.tool.execute({}, {"text": "今天天气不错"})

        # 应该返回原文本或尝试规范化
        assert result["normalized_text"] is not None
        # 没有可提取的实体
        assert result["entities"] == {}

    # ========== RAG检索测试 ==========

    def test_retrieve_examples_runway(self):
        """测试检索跑道相关示例"""
        examples = self.normalizer.retrieve_examples("跑道洞两左", top_k=3)

        assert len(examples) > 0
        # 应该检索到包含跑道的示例
        assert any("跑道" in ex.get("input", "") for ex in examples)

    def test_retrieve_examples_stand(self):
        """测试检索机位相关示例"""
        examples = self.normalizer.retrieve_examples("五洞幺机位", top_k=3)

        assert len(examples) > 0
        # 应该检索到包含机位的示例
        assert any("机位" in ex.get("input", "") for ex in examples)

    def test_retrieve_examples_flight(self):
        """测试检索航班号相关示例"""
        examples = self.normalizer.retrieve_examples("川航三幺拐拐", top_k=3)

        assert len(examples) > 0
        # 应该检索到包含航班号的示例
        assert any(any(airline in ex.get("input", "") for airline in ["川航", "国航", "东航"]) for ex in examples)

    # ========== Fallback机制测试 ==========

    def test_llm_failure_fallback(self, monkeypatch):
        """测试LLM失败时的Fallback机制"""
        # Mock LLM 抛出异常
        def mock_invoke(*args, **kwargs):
            raise Exception("LLM服务不可用")

        tool = RadiotelephonyNormalizerTool()
        if tool.normalizer.llm:
            monkeypatch.setattr(tool.normalizer.llm, "invoke", mock_invoke)

        result = tool.execute({}, {"text": "川航三幺拐拐"})

        # 应该返回原文本
        assert result["normalized_text"] == "川航三幺拐拐"
        assert result["confidence"] == 0.5
        assert "失败" in result["observation"]


# ========== 运行测试 ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
