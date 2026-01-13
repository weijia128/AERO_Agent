"""
航空读法规范化工具

职责：
- 将航空无线电读法转换为标准数据格式
- 使用 LLM + RAG 知识库提升准确性
- 输出可直接用于后续分析的标准化实体

示例：
输入: "川航三幺拐拐 跑道洞两左 报告鸟击"
输出: {
    "normalized_text": "川航3U3177 跑道02L 报告鸟击",
    "entities": {
        "flight_no": "3U3177",
        "position": "02L",
        "event_type": "bird_strike"
    }
}
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from tools.base import BaseTool
from config.llm_config import get_llm_client

logger = logging.getLogger(__name__)


class RadiotelephonyNormalizer:
    """航空读法规范化引擎 (LLM + RAG)"""

    def __init__(self):
        self.rules = self._load_rules()
        self.llm = None  # 懒加载

    def _load_rules(self) -> Dict[str, Any]:
        """加载规则文档"""
        rules_path = Path(__file__).parents[2] / "Radiotelephony_ATC.json"

        if not rules_path.exists():
            logger.warning(f"规则文件不存在: {rules_path}")
            return {}

        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载规则文件失败: {e}")
            return {}

    def retrieve_examples(self, input_text: str, top_k: int = 3) -> List[Dict]:
        """检索最相似的规范化示例 (用于 Few-shot)"""
        examples = self.rules.get("normalization_examples", [])

        if not examples:
            return []

        # 简单关键词匹配 (阶段1快速实现)
        keywords = self._extract_keywords(input_text)
        matched_examples = []

        for example in examples:
            score = self._calculate_similarity(keywords, example["input"])
            matched_examples.append((score, example))

        # 返回 top_k 个最相似示例
        matched_examples.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in matched_examples[:top_k]]

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词用于匹配"""
        keywords = []

        # 位置类型关键词
        if "跑道" in text or "runway" in text.lower():
            keywords.append("runway")
        if "滑行道" in text or "taxiway" in text.lower():
            keywords.append("taxiway")
        if "机位" in text or "stand" in text.lower():
            keywords.append("stand")

        # 航空公司关键词
        airline_codes = self.rules.get("normalization_rules", {}).get("flight_formats", {}).get("airline_codes", {})
        for airline in airline_codes.keys():
            if airline in text:
                keywords.append("flight")
                break

        # 事件类型关键词
        if any(kw in text for kw in ["漏油", "泄漏", "燃油", "液压", "滑油"]):
            keywords.append("oil_spill")
        if any(kw in text for kw in ["鸟击", "撞鸟"]):
            keywords.append("bird_strike")

        return keywords

    def _calculate_similarity(self, keywords: List[str], example_text: str) -> float:
        """计算相似度分数"""
        if not keywords:
            return 0.0

        score = 0.0
        for keyword in keywords:
            if keyword == "runway" and "跑道" in example_text:
                score += 1.0
            elif keyword == "taxiway" and "滑行道" in example_text:
                score += 1.0
            elif keyword == "stand" and "机位" in example_text:
                score += 1.0
            elif keyword == "flight" and any(airline in example_text for airline in ["川航", "国航", "东航", "南航"]):
                score += 1.0
            elif keyword == "oil_spill" and any(kw in example_text for kw in ["漏油", "泄漏"]):
                score += 0.5
            elif keyword == "bird_strike" and "鸟击" in example_text:
                score += 0.5

        return score / max(len(keywords), 1)

    def normalize_with_llm(self, text: str, timeout: int = 5) -> Dict[str, Any]:
        """使用 LLM 进行语义规范化"""
        if not self.llm:
            self.llm = get_llm_client()

        # 1. 检索相似示例
        examples = self.retrieve_examples(text, top_k=3)

        # 2. 构建 Few-shot 提示词
        prompt = self._build_prompt(text, examples)

        # 3. 调用 LLM
        try:
            response = self.llm.invoke(prompt, timeout=timeout)
            content = response.content if hasattr(response, 'content') else str(response)

            # 4. 解析结果
            result = self._parse_llm_response(content)
            return result

        except Exception as e:
            logger.warning(f"LLM 规范化失败: {e}")
            raise

    def _build_prompt(self, text: str, examples: List[Dict]) -> str:
        """构建 Few-shot 提示词"""
        # 格式化示例
        example_str = ""
        if examples:
            example_parts = []
            for ex in examples:
                entities_json = json.dumps(ex.get("extracted", {}), ensure_ascii=False)
                example_parts.append(f"输入: {ex['input']}\n输出: {entities_json}")
            example_str = "\n\n".join(example_parts)

        # 加载规则
        rules = self.rules.get("normalization_rules", {})

        return f"""你是航空无线电读法规范化专家。请将航空读法转换为标准数据格式。

【转换规则】:
1. 数字读法:
   洞→0, 幺→1, 两→2, 三→3, 四→4, 五→5, 六→6, 拐→7, 八→8, 九→9

2. 跑道格式:
   "跑道洞两左" → 位置: "02L"
   "跑道幺八右" → 位置: "18R"
   "跑道洞九中" → 位置: "09C"

3. 机位格式:
   "五洞幺机位" → 位置: "501"
   "三两号机位" → 位置: "32"

4. 滑行道格式:
   "滑行道A三" → 位置: "A3"
   "滑行道W两" → 位置: "W2"

5. 航班号格式:
   "川航三幺拐拐" → 航班号: "3U3177"
   "国航幺两三四" → 航班号: "CA1234"

【Few-shot示例】:
{example_str if example_str else "无相似示例"}

【待转换文本】:
{text}

请输出JSON格式 (只输出JSON，不要其他内容):
{{
    "normalized_text": "规范化后的完整文本",
    "entities": {{
        "flight_no": "标准航班号(如果有)",
        "position": "标准位置ID(如果有)",
        "fluid_type": "油液类型(如果有，FUEL/HYDRAULIC/OIL)",
        "engine_status": "发动机状态(如果有，RUNNING/STOPPED)",
        "event_type": "事件类型(如果有)"
    }},
    "confidence": 0.95
}}

注意:
- 如果某个字段不存在，不要输出该字段
- normalized_text 必须包含数字和位置的标准格式
- confidence 表示转换的置信度 (0.0-1.0)
"""

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON"""
        # 尝试提取 JSON 块
        content = content.strip()

        # 移除可能的 markdown 代码块标记
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            content = content.replace("```json", "").replace("```", "").strip()

        try:
            result = json.loads(content)

            # 验证必需字段
            if "normalized_text" not in result:
                raise ValueError("缺少 normalized_text 字段")

            # 确保 entities 存在
            if "entities" not in result:
                result["entities"] = {}

            # 设置默认置信度
            if "confidence" not in result:
                result["confidence"] = 0.8

            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}\n内容: {content}")
            raise ValueError(f"LLM 返回的不是有效 JSON: {content[:100]}")


class RadiotelephonyNormalizerTool(BaseTool):
    """航空读法规范化工具"""

    name = "normalize_radiotelephony"
    description = """将航空无线电读法转换为标准数据格式。

    输入: "川航三幺拐拐 跑道洞两左 报告鸟击"
    输出: {
        "normalized_text": "川航3U3177 跑道02L 报告鸟击",
        "entities": {
            "flight_no": "3U3177",
            "position": "02L",
            "event_type": "bird_strike"
        }
    }

    支持转换:
    - 数字读法: 洞/幺/两/拐 → 0/1/2/7
    - 航班号: 川航三幺拐拐 → 3U3177
    - 位置: 跑道洞两左 → 02L, 五洞幺机位 → 501
    """

    def __init__(self):
        super().__init__()
        self.normalizer = RadiotelephonyNormalizer()

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行规范化"""
        text = inputs.get("text", "")

        if not text:
            return {
                "observation": "无输入文本",
                "normalized_text": "",
                "entities": {},
                "confidence": 0.0
            }

        # 基础规范化 (已在 input_parser 中完成)
        # 这里直接使用 LLM 规范化

        try:
            result = self.normalizer.normalize_with_llm(text, timeout=5)

            observation = f"✓ 规范化完成\n原文: {text}\n标准: {result['normalized_text']}"
            if result.get("entities"):
                entities_str = ", ".join([f"{k}={v}" for k, v in result["entities"].items()])
                observation += f"\n提取: {entities_str}"

            return {
                "observation": observation,
                "normalized_text": result["normalized_text"],
                "entities": result.get("entities", {}),
                "confidence": result.get("confidence", 0.8)
            }

        except Exception as e:
            # Fallback: 返回原文本
            logger.warning(f"规范化失败，使用原文本: {e}")
            return {
                "observation": f"✗ 规范化失败 ({e})，使用原文本",
                "normalized_text": text,
                "entities": {},
                "confidence": 0.5
            }
