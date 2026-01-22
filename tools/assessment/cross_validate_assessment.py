"""
交叉验证风险评估工具

混合验证系统：规则引擎 + LLM 交叉验证

核心思路：
1. 规则引擎计算确定性结果（结果A）
2. LLM 推理验证（结果B）
3. 一致性检查
4. 冲突解决策略
5. 最终输出（含验证报告）
"""
import json
import logging
import random
from typing import Dict, Any, Tuple, Optional, cast
from datetime import datetime

from tools.base import BaseTool
from tools.assessment.assess_oil_spill_risk import AssessRiskTool
from config.llm_config import LLMConfig, LLMClientFactory
from agent.llm_guard import invoke_llm
from config.validation_config import ValidationConfig
from agent.state import RiskLevel, normalize_risk_level

logger = logging.getLogger(__name__)


class CrossValidateRiskTool(BaseTool):
    """交叉验证风险评估工具"""

    name = "assess_risk"
    description = """基于规则引擎 + LLM 交叉验证评估漏油事件的风险等级。

输入参数（可选，默认从状态获取）:
- fluid_type: 油液类型
- continuous: 是否持续
- engine_status: 发动机状态
- leak_size: 泄漏面积

返回信息:
- 风险等级 (R1-R4)
- 风险分数
- 验证报告（一致性、冲突、置信度）
- 立即行动建议"""

    def __init__(self):
        super().__init__()
        # 初始化规则引擎工具
        self.rule_engine_tool = AssessRiskTool()

        # 初始化 LLM 客户端（验证专用配置）
        validation_llm_config = LLMConfig(
            temperature=ValidationConfig.VALIDATION_TEMPERATURE,
            max_tokens=ValidationConfig.VALIDATION_MAX_TOKENS,
        )
        self.llm_client = LLMClientFactory.create_client(validation_llm_config)

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行交叉验证"""

        # ============================================================
        # 检查是否启用交叉验证
        # ============================================================
        if not ValidationConfig.ENABLE_CROSS_VALIDATION:
            logger.info("交叉验证已禁用，回退到纯规则引擎")
            return cast(Dict[str, Any], self.rule_engine_tool.execute(state, inputs))

        # ============================================================
        # 采样率控制（成本优化）
        # ============================================================
        if random.random() > ValidationConfig.SAMPLING_RATE:
            logger.info(f"采样率控制：跳过验证（采样率={ValidationConfig.SAMPLING_RATE}）")
            return cast(Dict[str, Any], self.rule_engine_tool.execute(state, inputs))

        # ============================================================
        # 第1步：规则引擎评估（确定性）
        # ============================================================
        rule_result = self.rule_engine_tool.execute(state, inputs)
        rule_assessment = rule_result.get("risk_assessment", {})
        rule_level = rule_assessment.get("level", "R2")
        rule_score = rule_assessment.get("score", 50)

        # ============================================================
        # 第2步：LLM 推理验证
        # ============================================================
        try:
            llm_result = self._llm_validate_risk(state, inputs, rule_level, rule_score)
            llm_level = str(llm_result.get("level") or rule_level)
            llm_confidence = llm_result.get("confidence", 0.0)
            llm_reasoning = llm_result.get("reasoning", "")
        except Exception as e:
            # LLM 验证失败时，记录错误并回退到规则引擎
            logger.error(f"LLM 验证失败: {e}")
            llm_level = rule_level  # 回退到规则结果
            llm_confidence = 0.0  # 低置信度
            llm_reasoning = f"LLM 验证失败: {str(e)}"

        # ============================================================
        # 第3步：一致性检查
        # ============================================================
        is_consistent, conflict_details = self._check_consistency(
            rule_level, llm_level, rule_score, llm_confidence
        )

        # ============================================================
        # 第4步：冲突解决策略
        # ============================================================
        final_level, resolution_strategy = self._resolve_conflict(
            rule_level=rule_level,
            llm_level=llm_level,
            llm_confidence=llm_confidence,
            is_consistent=is_consistent,
            conflict_details=conflict_details,
        )

        # ============================================================
        # 第5步：构建验证报告
        # ============================================================
        validation_report = {
            "timestamp": datetime.now().isoformat(),
            "rule_engine": {
                "level": rule_level,
                "score": rule_score,
                "factors": rule_assessment.get("factors", []),
                "rationale": rule_assessment.get("rationale", ""),
            },
            "llm_validation": {
                "level": llm_level,
                "confidence": llm_confidence,
                "reasoning": llm_reasoning,
            },
            "consistency": {
                "is_consistent": is_consistent,
                "conflict_details": conflict_details,
            },
            "final_decision": {
                "level": final_level,
                "resolution_strategy": resolution_strategy,
            },
            "needs_manual_review": self._check_manual_review_needed(
                is_consistent, llm_confidence, conflict_details
            ),
        }

        # ============================================================
        # 记录验证结果（监控和审计）
        # ============================================================
        if ValidationConfig.LOG_ALL_VALIDATIONS:
            logger.info(f"交叉验证完成: {json.dumps(validation_report, ensure_ascii=False)}")

        if ValidationConfig.LOG_CONFLICTS and not is_consistent:
            logger.warning(f"检测到冲突: {conflict_details}")

        # ============================================================
        # 构建最终输出
        # ============================================================
        observation = self._build_observation(
            final_level=final_level,
            rule_level=rule_level,
            llm_level=llm_level,
            is_consistent=is_consistent,
            llm_confidence=llm_confidence,
            resolution_strategy=resolution_strategy,
        )

        # 使用最终等级更新风险评估
        final_assessment = rule_assessment.copy()
        final_assessment["level"] = final_level
        final_assessment["validation_report"] = validation_report

        return {
            "observation": observation,
            "risk_assessment": final_assessment,
            "validation_report": validation_report,
            "mandatory_actions_done": {
                "risk_assessed": True,
            },
        }

    def _llm_validate_risk(
        self, state: Dict[str, Any], inputs: Dict[str, Any], rule_level: str, rule_score: int
    ) -> Dict[str, Any]:
        """
        使用 LLM 验证风险评估

        返回:
        {
            "level": "R3",
            "confidence": 0.85,
            "reasoning": "..."
        }
        """
        # 合并输入和状态中的事件信息
        incident = state.get("incident", {}).copy()
        incident.update(inputs)

        # 构建验证 prompt
        prompt = f"""你是机场应急风险评估专家。请验证以下漏油事件的风险等级。

事件信息:
- 油液类型: {incident.get('fluid_type', '未知')}
- 泄漏面积: {incident.get('leak_size', '未知')}
- 是否持续泄漏: {incident.get('continuous', '未知')}
- 发动机状态: {incident.get('engine_status', '未知')}

规则引擎评估结果:
- 风险等级: {rule_level}
- 风险分数: {rule_score}

风险等级定义:
- R1 (低风险): 分数 0-29，轻微泄漏，无火灾风险
- R2 (中等风险): 分数 30-54，需要专业处置，有一定影响
- R3 (高风险): 分数 55-74，需要立即响应，影响较大
- R4 (严重风险): 分数 75-100，极高火灾风险，需要紧急响应

请输出 JSON 格式:
{{
    "level": "R1|R2|R3|R4",
    "confidence": 0.0-1.0,
    "reasoning": "你的推理过程"
}}

要求:
1. 基于事件信息独立推理，判断风险等级
2. 输出置信度（0.0-1.0）
3. 说明推理依据
4. 只输出 JSON，不要其他内容
"""

        try:
            # 调用 LLM
            response = invoke_llm(prompt, llm=self.llm_client)
            content = response.content if hasattr(response, "content") else str(response)

            # 解析 JSON 响应
            result = cast(Dict[str, Any], json.loads(content.strip()))

            # 验证字段
            level = result.get("level", "R2")
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "")

            # 标准化风险等级
            level = normalize_risk_level(level)

            return {
                "level": level,
                "confidence": confidence,
                "reasoning": reasoning,
            }

        except Exception as e:
            logger.error(f"LLM 验证失败: {e}")
            # 验证失败时返回低置信度结果
            return {
                "level": rule_level,  # 回退到规则引擎结果
                "confidence": 0.0,
                "reasoning": f"LLM 验证失败: {str(e)}",
            }

    def _check_consistency(
        self, rule_level: str, llm_level: Optional[str], rule_score: int, llm_confidence: float
    ) -> Tuple[bool, str]:
        """
        检查一致性

        返回: (is_consistent, conflict_details)
        """
        # 如果 LLM 置信度过低，视为无效验证
        if llm_confidence < ValidationConfig.CONFIDENCE_THRESHOLD:
            return True, f"LLM 置信度过低 ({llm_confidence:.2f} < {ValidationConfig.CONFIDENCE_THRESHOLD})，忽略验证结果"

        # 如果 LLM 未返回有效等级
        if not llm_level or llm_level == "UNKNOWN":
            return True, "LLM 未返回有效风险等级"

        # 比较风险等级
        if rule_level == llm_level:
            return True, "规则引擎与 LLM 评估一致"

        # 计算风险等级差异
        level_diff = self._calculate_level_difference(rule_level, llm_level)

        conflict_details = (
            f"规则引擎评估为 {rule_level}，LLM 评估为 {llm_level}，"
            f"相差 {level_diff} 级，LLM 置信度 {llm_confidence:.2f}"
        )

        return False, conflict_details

    def _calculate_level_difference(self, level1: str, level2: str) -> int:
        """计算两个风险等级的差异（绝对值）"""
        level_order = {"R1": 1, "R2": 2, "R3": 3, "R4": 4}

        val1 = level_order.get(level1, 2)
        val2 = level_order.get(level2, 2)

        return abs(val1 - val2)

    def _resolve_conflict(
        self,
        rule_level: str,
        llm_level: str,
        llm_confidence: float,
        is_consistent: bool,
        conflict_details: str,
    ) -> Tuple[str, str]:
        """
        冲突解决策略

        返回: (final_level, resolution_strategy)
        """
        # 一致性检查通过 → 采用规则结果
        if is_consistent:
            return rule_level, "一致性验证通过，采用规则引擎结果"

        # LLM 置信度过低 → 忽略 LLM，采用规则结果
        if llm_confidence < ValidationConfig.CONFIDENCE_THRESHOLD:
            return rule_level, f"LLM 置信度过低 ({llm_confidence:.2f})，忽略验证结果"

        # LLM 置信度高 → 进一步判断
        if llm_confidence >= ValidationConfig.HIGH_CONFIDENCE_THRESHOLD:
            # 计算差异
            level_diff = self._calculate_level_difference(rule_level, llm_level)

            # 差异过大（>=2级）→ 标记为需要人工复核
            if level_diff >= ValidationConfig.RISK_LEVEL_DIFF_THRESHOLD:
                if ValidationConfig.USE_STRICTER_ON_CONFLICT:
                    # 采用更严格的评级（保守策略）
                    final_level = self._get_stricter_level(rule_level, llm_level)
                    return final_level, f"差异过大 ({level_diff} 级)，采用更严格评级: {final_level}（需人工复核）"
                else:
                    return rule_level, f"差异过大 ({level_diff} 级)，保留规则结果（需人工复核）"

            # 差异适中（1级）→ 采用更严格的评级
            if ValidationConfig.USE_STRICTER_ON_CONFLICT:
                final_level = self._get_stricter_level(rule_level, llm_level)
                return final_level, f"LLM 高置信度验证 ({llm_confidence:.2f})，采用更严格评级: {final_level}"
            else:
                return rule_level, "保留规则引擎结果"

        # LLM 置信度中等 → 保留规则结果
        return rule_level, f"LLM 置信度中等 ({llm_confidence:.2f})，保留规则引擎结果"

    def _get_stricter_level(self, level1: str, level2: str) -> str:
        """返回两个风险等级中更严格的一个"""
        level_order = {"R1": 1, "R2": 2, "R3": 3, "R4": 4}

        val1 = level_order.get(level1, 2)
        val2 = level_order.get(level2, 2)

        # 返回数值更大的等级（更严格）
        return level1 if val1 >= val2 else level2

    def _check_manual_review_needed(
        self, is_consistent: bool, llm_confidence: float, conflict_details: str
    ) -> bool:
        """判断是否需要人工复核"""
        if not ValidationConfig.ENABLE_MANUAL_REVIEW_FLAG:
            return False

        # 不一致 + 高置信度 → 需要人工复核
        if not is_consistent and llm_confidence >= ValidationConfig.HIGH_CONFIDENCE_THRESHOLD:
            return True

        return False

    def _build_observation(
        self,
        final_level: str,
        rule_level: str,
        llm_level: Optional[str],
        is_consistent: bool,
        llm_confidence: float,
        resolution_strategy: str,
    ) -> str:
        """构建观测结果"""
        lines = []
        lines.append(f"风险评估完成（交叉验证）: 最终等级={final_level}")

        lines.append(f"  规则引擎: {rule_level}")
        lines.append(f"  LLM 验证: {llm_level} (置信度={llm_confidence:.2f})")

        if is_consistent:
            lines.append("  ✓ 验证一致")
        else:
            lines.append(f"  ⚠️  检测到冲突: {resolution_strategy}")

        return "\n".join(lines)


# 导出工具类
__all__ = ["CrossValidateRiskTool"]
