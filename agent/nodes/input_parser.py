"""
输入解析节点

职责：
1. 解析用户输入
2. 识别场景类型
3. 提取实体信息（混合：正则 + LLM）
4. 初始化 Checklist 状态
"""
import concurrent.futures
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from agent.state import AgentState, FSMState
from config.llm_config import get_llm_client
from config.settings import settings
from config.airline_codes import AIRLINE_CHINESE_TO_IATA
from scenarios.base import ScenarioRegistry
from agent.nodes.semantic_understanding import (
    understand_conversation,
    split_by_confidence,
    DEFAULT_CONFIDENCE_THRESHOLDS,
)


# 通用实体提取正则（场景通用部分）
BASE_PATTERNS = {
    "position": [
        r"(\d{1,3})\s*(?:滑行道)",  # 12滑行道 -> 12
        r"(\d{2,3})\s*(?:机位|停机位)",  # 501机位, 32停机位 (数字在前)
        r"(?:在|位于)?(?:机位|停机位)\s*号?\s*(\d{2,3})",  # 在32号机位, 501停机位, 机位32
        r"(滑行道|TWY)[_\s]?([A-Z]?\d+)",  # 滑行道W2, TWY A3 (保留完整位置)
        r"(跑道|RWY)[_\s]?(\d{1,2}[LRC]?)",  # 跑道01L, 跑道2, RWY 09R (保留完整位置)
        r"(\d{2,3})\s*号",  # 234号（单独出现）
    ],
    "fluid_type": [
        (r"液压油|液压液|hydraulic", "HYDRAULIC"),  # 先匹配液压油
        (r"滑油|润滑油|机油|oil", "OIL"),  # 再匹配滑油
        (r"燃油|航油|油料|jet|fuel|漏油|泄漏", "FUEL"),  # 最后匹配燃油
    ],
    "engine_status": [
        # 优先匹配"未关闭"、"没关"等双重否定（表示运转中）
        (r"发动机.{0,5}(?:未|没有?).{0,3}(?:关闭?|停)", "RUNNING"),
        # 匹配运转状态（包括"运转"、"在运转"、"还在运转"等）
        (r"发动机.{0,5}(?:在|还在|正在)?\s*运转", "RUNNING"),
        # 匹配转的状态（包括"转"、"在转"、"还在转"等）
        (r"发动机.{0,5}(?:在|还在|正在)?.{0,3}转(?![工作])", "RUNNING"),
        # 匹配其他明确的运转状态（运行、工作、启动）
        (r"发动机.{0,5}(?:在|还在|正在)?.{0,3}(?:运行|工作|启动)", "RUNNING"),
        # 匹配关闭状态（带"发动机"前缀）
        (r"发动机.{0,5}(?:已关|已停|停了|关了|关闭|熄火)", "STOPPED"),
        # 匹配关闭状态（不带"发动机"前缀，但在上下文中提到发动机相关词）
        (r"(?:已关|已停|停了|关了|关闭|熄火|停车)", "STOPPED"),
        # 匹配运转状态（不带"发动机"前缀）
        (r"(?<!不|没)(?:运转|运行|在转|启动中)(?!了|止)", "RUNNING"),
    ],
    "continuous": [
        (r"(?:还在|持续|不断|一直).{0,3}(?:漏|滴|流)", True),
        (r"(?:已经|已|停止).{0,3}(?:不漏|停了|止住)", False),
    ],
    "leak_size": [
        (r"大面积|很大|大量|>5㎡|大于5", "LARGE"),
        (r"中等|一般|1-5㎡|1到5㎡", "MEDIUM"),
        (r"小面积|很小|少量|一点|<1㎡|小于1", "SMALL"),
        (r"(?:面积)?(?:不明|不清楚|不知道|待确认|未知|无法确定)", "UNKNOWN"),
    ],
    "aircraft": [
        r"航班(?:号)?[：:\s]*([A-Z]{2}\d{3,4})",  # 航班CES2355, 航班号: CA1234
        r"([A-Z]{2}\d{3,4})(?=\D|$)",  # CA1234 后面是非数字或结尾
        # 中文航空公司 + 航班号
        r"(?:国航|东航|南航|海航|川航|厦航|深航|山航|昆航|顺丰|圆通|中货航)\s*(\d{3,4})",  # 国航3242, 东航5678
        r"([B]-\d{4,5})",  # B-1234
    ],
}

_RADIOTELEPHONY_RULES = None


def _build_incident_and_checklist_templates(scenario_type: str) -> tuple[Dict[str, Any], Dict[str, bool]]:
    """根据场景配置构建 incident/checklist 模板，便于切换场景时重建字段。"""
    scenario = ScenarioRegistry.get(scenario_type)
    if not scenario:
        incident_fields = {
            "fluid_type": None,
            "continuous": None,
            "engine_status": None,
            "position": None,
            "leak_size": None,
            "flight_no": None,
            "reported_by": None,
            "report_time": datetime.now().isoformat(),
        }
        checklist_fields = {k: False for k in incident_fields.keys()}
        return incident_fields, checklist_fields

    incident_fields: Dict[str, Any] = {}
    checklist_fields: Dict[str, bool] = {}
    for field in scenario.p1_fields + scenario.p2_fields:
        key = field.get("key")
        if key:
            incident_fields[key] = None
            checklist_fields[key] = False
    incident_fields["report_time"] = datetime.now().isoformat()

    return incident_fields, checklist_fields


def _load_radiotelephony_rules() -> Dict[str, Any]:
    global _RADIOTELEPHONY_RULES
    if _RADIOTELEPHONY_RULES is not None:
        return _RADIOTELEPHONY_RULES

    rules_path = (
        Path(__file__).resolve().parents[2] / "data" / "raw" / "Radiotelephony_ATC.json"
    )
    if not rules_path.exists():
        _RADIOTELEPHONY_RULES = {}
        return _RADIOTELEPHONY_RULES

    try:
        with rules_path.open("r", encoding="utf-8") as f:
            _RADIOTELEPHONY_RULES = json.load(f)
    except json.JSONDecodeError:
        _RADIOTELEPHONY_RULES = {}

    return _RADIOTELEPHONY_RULES


def normalize_radiotelephony_text(text: str) -> str:
    rules = _load_radiotelephony_rules()
    if not rules:
        return text

    digits_map = rules.get("digits", {})
    letters_map = rules.get("letters", {})
    if not digits_map and not letters_map:
        return text

    normalized = text

    if letters_map:
        for letter, spoken in letters_map.items():
            if spoken:
                normalized = normalized.replace(spoken, letter)

    if digits_map:
        reverse_digits = {v: k for k, v in digits_map.items()}
        for spoken, digit in reverse_digits.items():
            if spoken:
                normalized = normalized.replace(spoken, digit)

        normalized = re.sub(r"(?<=[A-Z0-9])\s+(?=[A-Z0-9])", "", normalized)

    # 规范"数字+滑行道/跑道/机位"顺序为"滑行道12"形式
    normalized = re.sub(
        r"\b(\d{1,3})\s*(滑行道|跑道|机位)",
        lambda m: f"{m.group(2)}{m.group(1)}",
        normalized,
    )

    # 将"跑道27左/右/中"转换为标准ICAO格式"跑道27L/R/C"
    # 避免后续"左发/右发"误匹配（如"跑道27左发生鸟击"中的"左"应属于跑道编号）
    normalized = re.sub(
        r"(跑道\d{1,2})(左|右|中)",
        lambda m: f"{m.group(1)}{'L' if m.group(2) == '左' else 'R' if m.group(2) == '右' else 'C'}",
        normalized,
    )

    return normalized


def _format_position_display(position: str, raw_text: str) -> str:
    """生成用于展示的位置文本（尽量保留跑道语义）"""
    if not position:
        return position
    pos = position.strip()
    if "跑道" in pos:
        return pos
    if re.search(r"(跑道|RWY|RUNWAY)", raw_text, re.IGNORECASE) and re.fullmatch(r"\d{2}[LRC]?", pos):
        return f"跑道{pos}"
    return pos


def _extract_entities_legacy(text: str) -> Dict[str, Any]:
    """从文本中提取实体（旧版，兼容保留）"""
    entities = {}

    # 提取位置 - 增强模式
    for pattern in BASE_PATTERNS["position"]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # 如果有两个捕获组（如滑行道、跑道），组合完整位置
            if len(match.groups()) == 2:
                prefix, suffix = match.group(1), match.group(2)
                # 修复：统一不加空格，保持紧凑格式（如"跑道2"、"滑行道19"）
                entities["position"] = f"{prefix}{suffix}"
            else:
                entities["position"] = match.group(1)
            break

    # 如果没提取到位置，尝试更多fallback匹配模式
    if "position" not in entities:
        text_stripped = text.strip()

        # 1. 纯数字2-3位（如 "234", "501"）- 最常见的机位号格式
        if re.match(r'^\d{2,3}$', text_stripped):
            entities["position"] = text_stripped

        # 2. 用户只回答了位置类型和数字（如"跑道2"、"滑行道19"）
        elif re.match(r'^(跑道|滑行道|机位)\s*\d+', text_stripped, re.IGNORECASE):
            # 提取完整位置字符串，去除空格
            match = re.match(r'^(跑道|滑行道|机位)\s*(\d+)', text_stripped, re.IGNORECASE)
            if match:
                entities["position"] = f"{match.group(1)}{match.group(2)}"

        # 3. 用户在一句话中提到了位置（如"我在跑道2，发动机关闭"）
        else:
            # 尝试再次匹配跑道/滑行道+数字（不要求前后有特定词汇）
            match = re.search(r'(跑道|滑行道|机位|TWY|RWY)[_\s]?([A-Z]?\d+)', text, re.IGNORECASE)
            if match:
                entities["position"] = f"{match.group(1)}{match.group(2)}"
            else:
                # 最后尝试：纯数字（可能埋在其他文本中）
                match = re.search(r'\b(\d{2,3})\b', text)
                if match:
                    # 只在没有其他位置信息时才使用纯数字
                    entities["position"] = match.group(1)

    # 提取油液类型
    for pattern, value in BASE_PATTERNS["fluid_type"]:
        if re.search(pattern, text):
            entities["fluid_type"] = value
            break

    # 鸟击场景特有字段
    for pattern, value in BASE_PATTERNS.get("event_type", []):
        if re.search(pattern, text):
            entities["event_type"] = value
            break

    for pattern, value in BASE_PATTERNS.get("affected_part", []):
        if re.search(pattern, text):
            entities["affected_part"] = value
            break

    for pattern, value in BASE_PATTERNS.get("current_status", []):
        if re.search(pattern, text):
            entities["current_status"] = value
            break

    # 提取发动机状态
    for pattern, value in BASE_PATTERNS["engine_status"]:
        if re.search(pattern, text):
            entities["engine_status"] = value
            break

    # 提取是否持续
    for pattern, value in BASE_PATTERNS["continuous"]:
        if re.search(pattern, text):
            entities["continuous"] = value
            break

    # 提取面积大小
    for pattern, value in BASE_PATTERNS["leak_size"]:
        if re.search(pattern, text):
            entities["leak_size"] = value
            break

    # 提取航班号（不再提取机号）
    for pattern in BASE_PATTERNS["aircraft"]:
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            # 跳过机号格式（B-开头），只提取航班号
            if value.startswith("B-"):
                continue
            elif value.isdigit():
                # 可能是中文航空公司名称，需要查找是哪个
                for cn_name, code in AIRLINE_CHINESE_TO_IATA.items():
                    if cn_name in text:
                        # 保存原始显示格式（中文+数字）
                        entities["flight_no_display"] = f"{cn_name}{value}"
                        # 保存IATA格式用于转换
                        entities["flight_no"] = f"{code}{value}"
                        break
            else:
                # IATA或ICAO格式
                # 保存原始格式用于显示
                entities["flight_no_display"] = value
                entities["flight_no"] = value
            break

    return entities


def identify_scenario(text: str) -> str:
    """
    识别场景类型（基于场景注册的关键词，支持优先级）
    """
    text_lower = text.lower()
    candidates: list[tuple[int, str]] = []

    for name in ScenarioRegistry.list_all():
        scenario = ScenarioRegistry.get(name)
        if not scenario:
            continue
        keywords = getattr(scenario, "keywords", []) or []
        priority = scenario.metadata.get("priority", 100)
        if any(kw.lower() in text_lower for kw in keywords):
            candidates.append((priority, name))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # 回退：保持与历史逻辑一致
    oil_keywords = ["漏油", "泄漏", "燃油", "液压油", "滑油", "油液", "漏液"]
    bird_keywords = ["鸟击", "撞鸟", "鸟撞", "疑似鸟击"]
    if any(kw in text_lower for kw in bird_keywords):
        return "bird_strike"
    if any(kw in text_lower for kw in oil_keywords):
        return "oil_spill"

    return "oil_spill"


def update_checklist(incident: Dict[str, Any], base_checklist: Dict[str, bool] = None) -> Dict[str, bool]:
    """根据事件信息更新 Checklist 状态（保持场景字段）"""
    if base_checklist:
        return {k: incident.get(k) is not None for k in base_checklist.keys()}

    return {
        "flight_no": incident.get("flight_no") is not None,
        "fluid_type": incident.get("fluid_type") is not None,
        "continuous": incident.get("continuous") is not None,
        "engine_status": incident.get("engine_status") is not None,
        "position": incident.get("position") is not None,
        "leak_size": incident.get("leak_size") is not None,
    }


def _execute_future_with_timeout(
    future: concurrent.futures.Future,
    timeout: int = 10,
) -> Dict[str, Any] | None:
    """执行 future 并处理超时和异常"""
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.debug("Future execution timed out")
        return None
    except Exception as e:
        logger.debug("Future execution failed: %s", e)
        return None


def _fetch_aircraft_info(incident: Dict[str, Any], flight_no: str) -> Dict[str, Any]:
    """获取航班信息"""
    from tools.information.get_aircraft_info import GetAircraftInfoTool
    tool = GetAircraftInfoTool()
    return tool.execute(incident, {"flight_no": flight_no})


def _fetch_flight_plan(incident: Dict[str, Any], flight_no: str) -> Dict[str, Any]:
    """获取航班计划"""
    from tools.information.flight_plan_lookup import FlightPlanLookupTool
    tool = FlightPlanLookupTool()
    return tool.execute(incident, {"flight_no": flight_no})


def _fetch_stand_location(incident: Dict[str, Any]) -> Dict[str, Any]:
    """获取位置拓扑信息"""
    from tools.spatial.get_stand_location import GetStandLocationTool
    tool = GetStandLocationTool()
    return tool.execute(incident, {})


def _calculate_impact_zone(
    incident: Dict[str, Any],
    position: str,
    risk_level: str,
) -> Dict[str, Any]:
    """计算影响范围"""
    from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool
    tool = CalculateImpactZoneTool()
    impact_inputs = {
        "position": position,
        "fluid_type": incident.get("fluid_type"),
        "risk_level": risk_level,
    }
    return tool.execute(incident, impact_inputs)


def _analyze_position_impact(
    incident: Dict[str, Any],
    risk_assessment: Dict[str, Any],
) -> Dict[str, Any]:
    """分析位置影响"""
    from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool
    tool = AnalyzePositionImpactTool()
    temp_state = {
        "incident": incident,
        "risk_assessment": risk_assessment,
    }
    return tool.execute(temp_state, {})


def apply_auto_enrichment(
    state: AgentState,
    current_incident: Dict[str, Any],
) -> Dict[str, Any]:
    """根据已知信息自动补充航班、位置与影响分析（并行优化版）"""
    incident = dict(current_incident)
    updates: Dict[str, Any] = {}
    observations: list[str] = []

    position = incident.get("position")
    flight_no = incident.get("flight_no") or incident.get("flight_no_display", "")
    spatial_analysis = dict(state.get("spatial_analysis", {}) or {})

    # ========== 第一阶段：并行执行独立的信息查询 ==========
    phase1_futures: Dict[str, concurrent.futures.Future] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        if flight_no and not incident.get("airline"):
            phase1_futures["aircraft_info"] = executor.submit(
                _fetch_aircraft_info, incident, flight_no
            )

        if flight_no and not state.get("flight_plan_table"):
            phase1_futures["flight_plan"] = executor.submit(
                _fetch_flight_plan, incident, flight_no
            )

        if position and not spatial_analysis:
            phase1_futures["stand_location"] = executor.submit(
                _fetch_stand_location, incident
            )

        # 收集第一阶段结果
        for key, future in phase1_futures.items():
            result = _execute_future_with_timeout(future)
            if not result:
                continue

            if key == "aircraft_info" and result.get("incident"):
                for k, v in result["incident"].items():
                    if v and k not in incident:
                        incident[k] = v
                if result.get("observation"):
                    observations.append(f"\n航班信息: {result['observation']}")

            elif key == "flight_plan":
                if result.get("observation"):
                    observations.append(f"\n航班计划: {result['observation']}")
                    updates["flight_plan_observation"] = result["observation"]
                if result.get("flight_plan_table"):
                    updates["flight_plan_table"] = result["flight_plan_table"]

            elif key == "stand_location":
                if result.get("observation"):
                    observations.append(f"\n位置信息: {result['observation']}")
                if result.get("spatial_analysis"):
                    spatial_analysis.update(result["spatial_analysis"])

    # ========== 第二阶段：依赖第一阶段结果的计算 ==========
    phase2_futures: Dict[str, concurrent.futures.Future] = {}
    risk_level = state.get("risk_assessment", {}).get("level", "R2")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        if position and not incident.get("impact_zone"):
            phase2_futures["impact_zone"] = executor.submit(
                _calculate_impact_zone, incident, position, risk_level
            )

        if position and incident.get("fluid_type") and not state.get("position_impact_analysis"):
            risk_assessment = state.get("risk_assessment", {"level": "R2"})
            phase2_futures["position_impact"] = executor.submit(
                _analyze_position_impact, incident, risk_assessment
            )

        # 收集第二阶段结果
        position_impact_analysis: Dict[str, Any] = {}

        for key, future in phase2_futures.items():
            result = _execute_future_with_timeout(future)
            if not result:
                continue

            if key == "impact_zone":
                if result.get("observation"):
                    observations.append(f"\n影响范围: {result['observation']}")
                if result.get("spatial_analysis"):
                    for k, v in result["spatial_analysis"].items():
                        if k not in spatial_analysis:
                            spatial_analysis[k] = v
                    incident["impact_zone"] = result["spatial_analysis"]

            elif key == "position_impact":
                if result.get("observation"):
                    observations.append(f"\n{result['observation']}")
                if result.get("position_impact_analysis"):
                    position_impact_analysis = result["position_impact_analysis"]

    # ========== 汇总结果 ==========
    updates["incident"] = incident
    if spatial_analysis:
        updates["spatial_analysis"] = spatial_analysis
    if position_impact_analysis:
        updates["position_impact_analysis"] = position_impact_analysis
    if observations:
        updates["enrichment_observation"] = "".join(observations)

    return updates


def input_parser_node(state: AgentState) -> Dict[str, Any]:
    """
    输入解析节点

    职责：
    1. 从用户消息中提取实体
    2. 识别场景类型
    3. 更新 incident 和 checklist 状态
    4. 自动获取航班信息（如果航班号已知）
    """
    # 获取最新用户消息
    messages = state.get("messages", [])
    if not messages:
        return {
            "error": "没有收到用户输入",
            "next_node": "end",
        }

    # 获取用户输入
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        return {
            "error": "没有找到用户消息",
            "next_node": "end",
        }

    normalized_message = normalize_radiotelephony_text(user_message)

    # ========== 新增: 航空读法深度规范化 (LLM + RAG) ==========
    # 只对包含航空读法特征的输入进行LLM规范化，避免简短回答被错误处理
    from tools.information.radiotelephony_normalizer import RadiotelephonyNormalizerTool

    # 检查是否需要LLM规范化（包含航空读法词 OR 航空关键词且非简短回答）
    radiotelephony_keywords = ["洞", "幺", "两", "拐", "五"]
    aviation_keywords = ["跑道", "机位", "滑行道", "川航", "国航", "东航", "南航", "海航", "厦航"]

    has_radiotelephony = any(kw in normalized_message for kw in radiotelephony_keywords)
    has_aviation_context = any(kw in normalized_message for kw in aviation_keywords)

    needs_normalization = has_radiotelephony or (has_aviation_context and len(normalized_message) > 5)

    enhanced_message = normalized_message
    pre_extracted_entities = {}
    normalization_confidence = 0.0

    if needs_normalization:
        normalizer = RadiotelephonyNormalizerTool()
        normalization_result = normalizer.execute(state, {"text": normalized_message})

        # 使用增强后的文本 (Fallback: 如果失败使用原文本)
        enhanced_message = normalization_result.get("normalized_text", normalized_message)
        pre_extracted_entities = normalization_result.get("entities", {})
        normalization_confidence = normalization_result.get("confidence", 0.5)

        logger.info(f"航空读法规范化: {normalized_message} → {enhanced_message} (置信度: {normalization_confidence:.2f})")
        if pre_extracted_entities:
            logger.info(f"预提取实体: {pre_extracted_entities}")
    else:
        logger.debug(f"跳过LLM规范化（简短回答）: {normalized_message}")
    # ================================================================

    # 识别场景类型（一旦确定，完全锁定）
    current_scenario = state.get("scenario_type", "")
    if current_scenario:
        # 场景已锁定，不再重新识别
        scenario_type = current_scenario
        logger.info(f"场景已锁定: {scenario_type}")
    else:
        # 首次识别场景
        detected_scenario = identify_scenario(enhanced_message)
        scenario_type = detected_scenario
        logger.info(f"首次识别场景: {scenario_type}")

    # 构建对话历史上下文
    history = build_history_context(messages)

    # 基于场景模板重建 incident/checklist，保留已知字段
    incident_template, checklist_template = _build_incident_and_checklist_templates(scenario_type)
    current_incident = incident_template
    allowed_field_keys = _get_scenario_field_keys(scenario_type)

    # 只复制属于当前场景的字段
    for key, value in state.get("incident", {}).items():
        if value in [None, ""]:
            continue
        if key in allowed_field_keys and key in current_incident:
            current_incident[key] = value
        else:
            logger.debug(f"从旧state过滤掉不属于场景 {scenario_type} 的字段: {key}")
    semantic_understanding: Dict[str, Any] = {}
    semantic_validation: Dict[str, Any] = {}
    extracted: Dict[str, Any] = {}

    if settings.ENABLE_SEMANTIC_UNDERSTANDING:
        semantic_understanding = understand_conversation(
            current_message=normalized_message,
            conversation_history=messages,
            known_facts=current_incident,
            fsm_state=state.get("fsm_state", FSMState.INIT.value),
        )

        accepted, low_confidence_fields = split_by_confidence(
            semantic_understanding.get("extracted_facts", {}),
            semantic_understanding.get("confidence_scores", {}),
            DEFAULT_CONFIDENCE_THRESHOLDS,
        )

        # 基于规则的快速提取（更稳定），作为补充
        deterministic_entities = extract_entities(normalized_message, scenario_type)
        extracted.update(deterministic_entities)
        extracted.update(accepted)

        # 合并信息并记录潜在冲突
        semantic_issues = list(semantic_understanding.get("semantic_issues", []))
        for key, value in extracted.items():
            if value is None:
                continue
            if key not in allowed_field_keys:
                logger.warning(f"语义理解提取的字段 {key} 不属于场景 {scenario_type}，已忽略")
                continue

            previous_value = current_incident.get(key)
            if previous_value not in [None, ""] and previous_value != value:
                semantic_issues.append(f"{key} 与已知信息不一致，请确认")
            current_incident[key] = value

        # 语义验证结果（缺失/低置信度/矛盾）
        scenario = ScenarioRegistry.get(scenario_type)
        required_fields = _infer_required_fields(scenario, current_incident)

        checklist = update_checklist(current_incident, checklist_template)
        missing_fields = [field for field in required_fields if not checklist.get(field, False)]

        semantic_validation = {
            "missing_fields": missing_fields,
            "low_confidence_fields": low_confidence_fields,
            "semantic_issues": semantic_issues,
            "summary": semantic_understanding.get("conversation_summary", ""),
        }
    else:
        # 提取实体（混合方案：正则 + LLM，更灵活）
        extracted = extract_entities_hybrid(enhanced_message, history, scenario_type)

        # 先使用常规提取的结果，再用规范化工具覆盖
        for key, value in extracted.items():
            if value is not None and key in allowed_field_keys:
                current_incident[key] = value
            elif value is not None:
                logger.warning(f"字段 {key} 不属于场景 {scenario_type}，已忽略")

        # 规范化工具的结果优先级最高（LLM+RAG处理过）
        for key, value in pre_extracted_entities.items():
            if not value:
                continue
            if key not in allowed_field_keys:
                logger.warning(f"规范化工具提取的字段 {key} 不属于场景 {scenario_type}，已忽略")
                continue
            if key in current_incident and current_incident[key] != value:
                logger.info(f"规范化工具覆盖 {key}: {current_incident[key]} → {value}")
            current_incident[key] = value

    if current_incident.get("position"):
        current_incident["position_display"] = _format_position_display(
            current_incident.get("position", ""),
            user_message,
        )

    # 自动补充信息（航班、位置、影响分析等）
    enrichment = apply_auto_enrichment(state, current_incident)
    current_incident = enrichment.get("incident", current_incident)
    spatial_analysis = enrichment.get("spatial_analysis", {})
    position_impact_analysis = enrichment.get("position_impact_analysis", {})
    flight_plan_table = enrichment.get("flight_plan_table")
    flight_plan_observation = enrichment.get("flight_plan_observation")
    weather_info = enrichment.get("weather")  # 提取气象信息
    enrichment_observation = enrichment.get("enrichment_observation", "")  # 提取增强观察信息

    # 更新 checklist（保持场景字段）
    checklist = update_checklist(current_incident, checklist_template)
    if semantic_validation:
        scenario = ScenarioRegistry.get(scenario_type)
        required_fields = _infer_required_fields(scenario, current_incident)
        semantic_validation["missing_fields"] = [
            field for field in required_fields if not checklist.get(field, False)
        ]

    if not current_incident.get("reported_by"):
        reporter = ""
        reporter_keywords = [
            ("机坪管制", ["机坪管制", "机坪管制员"]),
            ("塔台", ["塔台", "管制", "ATC"]),
            ("场务", ["场务", "场务巡查", "巡查"]),
            ("机组", ["机组", "机长", "副驾驶", "飞行员"]),
            ("机务", ["机务", "维修", "航线"]),
            ("地服", ["地服", "地面保障", "保障单位"]),
            ("运控", ["运控", "运行指挥", "运行中心"]),
            ("安全监察", ["安全监察", "安监"]),
            ("安保", ["安保", "警卫", "公安"]),
            ("施工单位", ["施工", "外包", "承包商"]),
        ]
        for label, keywords in reporter_keywords:
            if any(k in user_message for k in keywords):
                reporter = label
                break
        flight_no_display = current_incident.get("flight_no_display") or current_incident.get("flight_no")
        current_incident["reported_by"] = reporter or flight_no_display or "——"

    # 记录解析结果
    observation_parts = []

    # 添加规范化信息
    if normalization_confidence > 0.7:
        observation_parts.append(f"航空读法规范化: {normalized_message} → {enhanced_message}")

    observation_parts.append(f"提取实体: {extracted}")

    if semantic_understanding:
        observation_parts.append(f"语义理解: {semantic_understanding.get('conversation_summary', '')}")
    if enrichment.get("enrichment_observation"):
        observation_parts.append(enrichment.get("enrichment_observation"))
    reasoning_step = {
        "step": 0,
        "thought": f"解析用户输入，识别为{scenario_type}场景",
        "action": "input_parser",
        "action_input": {"text": normalized_message, "raw_text": user_message},
        "observation": "\n".join(observation_parts),
        "timestamp": datetime.now().isoformat(),
    }

    existing_steps = state.get("reasoning_steps", [])
    reasoning_steps = existing_steps + [reasoning_step] if existing_steps else [reasoning_step]
    iteration_count = state.get("iteration_count", 0) or 1

    return {
        "scenario_type": scenario_type,
        "incident": current_incident,
        "checklist": checklist,
        "awaiting_user": False,
        **({"spatial_analysis": spatial_analysis} if spatial_analysis else {}),
        **({"position_impact_analysis": position_impact_analysis} if position_impact_analysis else {}),
        **({"flight_plan_table": flight_plan_table} if flight_plan_table else {}),
        **({"flight_plan_observation": flight_plan_observation} if flight_plan_observation else {}),
        **({"weather": weather_info} if weather_info else {}),  # 添加气象信息
        **({"enrichment_observation": enrichment_observation} if enrichment_observation else {}),  # 添加增强观察信息
        **({"normalization_result": normalization_result} if normalization_confidence > 0.7 else {}),  # 添加规范化结果
        "reasoning_steps": reasoning_steps,
        "current_node": "input_parser",
        "next_node": "reasoning",
        "iteration_count": iteration_count,
        **({"semantic_understanding": semantic_understanding} if semantic_understanding else {}),
        **({"semantic_validation": semantic_validation} if semantic_validation else {}),
    }


def build_history_context(messages: list) -> str:
    """构建对话历史上下文"""
    if not messages:
        return "无历史对话"

    context_parts = []
    for msg in messages[-5:]:  # 只取最近5条
        role = msg.get("role", "")
        content = msg.get("content", "")
        context_parts.append(f"{role}: {content}")

    return "\n".join(context_parts)


# ============================================================
# LLM 实体提取（更灵活的方案）
# ============================================================

LLM_EXTRACT_PROMPT = """你是一个机场应急响应系统的事件信息提取助手。

根据对话历史和当前用户输入，提取事件信息。输出 JSON 格式：

## 对话历史：
{history}

## 当前用户输入：
{user_input}

## 需要提取的字段：
- position: 事发位置（如 501、A3、01L 等，可只填数字表示机位号）
- location_area: 位置类别（RUNWAY=跑道, TAXIWAY=滑行道, APRON=机坪, UNKNOWN=不明）
- fod_type: FOD 种类（METAL=金属类, PLASTIC_RUBBER=塑料/橡胶, STONE_GRAVEL=石块/砂石, LIQUID=油液/液体, UNKNOWN=不明）
- presence: 是否仍在道面（ON_SURFACE=仍在道面, REMOVED=已移除, MOVING_BLOWING=被风吹动, UNKNOWN=不明）
- report_time: 汇报时间（自由文本，如 14:32）
- fod_size: FOD 尺寸（SMALL=<5cm, MEDIUM=5-15cm, LARGE=>15cm, UNKNOWN=不明，可返回描述）
- related_event: 是否与前序事件有关（YES/NO/UNKNOWN）
- fluid_type: 油液类型（FUEL=燃油, HYDRAULIC=液压油, OIL=滑油）
- engine_status: 发动机状态（RUNNING=运转中, STOPPED=已停止）
- continuous: 是否持续泄漏（true=是, false=否）
- leak_size: 泄漏面积（LARGE=大面积, MEDIUM=中等, SMALL=小面积, UNKNOWN=不明/不清楚）
- flight_no: 航班号（如 CA1234、MU5678）
- phase: 飞行阶段（PUSHBACK/TAXI/TAKEOFF_ROLL/INITIAL_CLIMB/CRUISE/DESCENT/APPROACH/LANDING_ROLL/ON_STAND/UNKNOWN）
- evidence: 迹象强度（CONFIRMED_STRIKE_WITH_REMAINS/SYSTEM_WARNING/ABNORMAL_NOISE_VIBRATION/SUSPECTED_ONLY/NO_ABNORMALITY）
- bird_info: 鸟类信息（LARGE_BIRD/FLOCK/MEDIUM_SMALL_SINGLE/UNKNOWN）
- ops_impact: 运行影响（RTO_OR_RTB/BLOCKING_RUNWAY_OR_TAXIWAY/REQUEST_MAINT_CHECK/NO_OPS_IMPACT/RUNWAY_CLOSED/TAXIWAY_BLOCKED/APRON_RESTRICTED/MINOR_IMPACT/NO_IMPACT/UNKNOWN）
- crew_request: 机组请求（自由文本，如返航/备降/检查/支援等）

## 智能提取规则：
1. 如果用户只输入纯数字（2-3位），且问题是关于位置的 → 识别为机位号
2. 如果用户输入航班号格式（2字母+3-4数字） → 识别为 flight_no
3. 如果用户回答"是/否/不知道"等，且没有明确信息 → 返回空 {}
4. **重要**：如果用户明确表示某个信息"不明"、"不清楚"、"不知道"，提取为 UNKNOWN（不要返回空）
5. 只提取明确的信息，不要猜测

## 输出格式：
{{"position": "...", "fluid_type": "FUEL", "engine_status": "RUNNING", "phase": "TAXI", ...}}

如果无法提取任何有效信息，返回 {{}}
"""

# 枚举值映射表
ENUM_VALUE_MAPS = {
    "fluid_type": {
        "valid_values": {"FUEL", "HYDRAULIC", "OIL", "UNKNOWN"},
        "mappings": {
            "燃油": "FUEL", "航油": "FUEL", "航空燃油": "FUEL", "jet": "FUEL", "fuel": "FUEL",
            "液压油": "HYDRAULIC", "液压": "HYDRAULIC", "hydraulic": "HYDRAULIC",
            "滑油": "OIL", "机油": "OIL", "润滑油": "OIL", "oil": "OIL",
        }
    },
    "engine_status": {
        "valid_values": {"RUNNING", "STOPPED", "UNKNOWN"},
        "mappings": {
            "运转": "RUNNING", "运行": "RUNNING", "在转": "RUNNING", "启动": "RUNNING",
            "停止": "STOPPED", "关闭": "STOPPED", "关车": "STOPPED", "熄火": "STOPPED",
        }
    },
    "leak_size": {
        "valid_values": {"LARGE", "MEDIUM", "SMALL", "UNKNOWN"},
        "mappings": {
            "大面积": "LARGE", "很大": "LARGE", "大量": "LARGE", ">5": "LARGE", "5㎡": "LARGE",
            "中等": "MEDIUM", "一般": "MEDIUM", "1-5": "MEDIUM",
            "小面积": "SMALL", "少量": "SMALL", "一点": "SMALL", "<1": "SMALL",
            "不明": "UNKNOWN", "不清楚": "UNKNOWN", "不知道": "UNKNOWN", "未知": "UNKNOWN", "待确认": "UNKNOWN",
        }
    },

    "location_area": {
        "valid_values": {"RUNWAY", "TAXIWAY", "APRON", "UNKNOWN"},
        "mappings": {
            "跑道": "RUNWAY", "RUNWAY": "RUNWAY", "RWY": "RUNWAY",
            "滑行道": "TAXIWAY", "TAXIWAY": "TAXIWAY", "TWY": "TAXIWAY",
            "机坪": "APRON", "停机坪": "APRON", "APRON": "APRON",
            "不明": "UNKNOWN", "未知": "UNKNOWN",
        }
    },
    "fod_type": {
        "valid_values": {"METAL", "PLASTIC_RUBBER", "STONE_GRAVEL", "LIQUID", "UNKNOWN"},
        "mappings": {
            "金属": "METAL", "螺母": "METAL", "螺栓": "METAL", "钉": "METAL", "工具": "METAL",
            "塑料": "PLASTIC_RUBBER", "橡胶": "PLASTIC_RUBBER", "轮胎": "PLASTIC_RUBBER",
            "PLASTIC": "PLASTIC_RUBBER", "RUBBER": "PLASTIC_RUBBER",
            "石块": "STONE_GRAVEL", "砂石": "STONE_GRAVEL", "碎石": "STONE_GRAVEL", "GRAVEL": "STONE_GRAVEL",
            "液体": "LIQUID", "油液": "LIQUID", "液体异物": "LIQUID",
            "不明": "UNKNOWN", "未知": "UNKNOWN",
        }
    },
    "presence": {
        "valid_values": {"ON_SURFACE", "REMOVED", "MOVING_BLOWING", "UNKNOWN"},
        "mappings": {
            "仍在": "ON_SURFACE", "在道面": "ON_SURFACE", "未移除": "ON_SURFACE",
            "已移除": "REMOVED", "已清理": "REMOVED", "已处理": "REMOVED",
            "被风吹动": "MOVING_BLOWING", "移动": "MOVING_BLOWING", "滚动": "MOVING_BLOWING",
            "不明": "UNKNOWN", "未知": "UNKNOWN",
        }
    },
    "fod_size": {
        "valid_values": {"SMALL", "MEDIUM", "LARGE", "UNKNOWN"},
        "mappings": {
            "小": "SMALL", "<5CM": "SMALL", "小于5": "SMALL",
            "中": "MEDIUM", "5-15CM": "MEDIUM", "5~15": "MEDIUM",
            "大": "LARGE", ">15CM": "LARGE", "大于15": "LARGE",
            "不明": "UNKNOWN", "未知": "UNKNOWN",
        }
    },
    "related_event": {
        "valid_values": {"YES", "NO", "UNKNOWN"},
        "mappings": {
            "是": "YES", "有关": "YES", "相关": "YES",
            "否": "NO", "无关": "NO", "不是": "NO",
            "不明": "UNKNOWN", "未知": "UNKNOWN",
        }
    },
    "phase": {
        "valid_values": {"PUSHBACK", "TAXI", "TAKEOFF_ROLL", "INITIAL_CLIMB", "CRUISE", "DESCENT", "APPROACH", "LANDING_ROLL", "ON_STAND", "UNKNOWN"},
        "mappings": {
            "推出": "PUSHBACK",
            "滑行": "TAXI",
            "起飞滑跑": "TAKEOFF_ROLL",
            "起飞": "TAKEOFF_ROLL",
            "爬升": "INITIAL_CLIMB",
            "起飞后": "INITIAL_CLIMB",
            "巡航": "CRUISE",
            "下降": "DESCENT",
            "进近": "APPROACH",
            "落地滑跑": "LANDING_ROLL",
            "着陆滑跑": "LANDING_ROLL",
            "停机位": "ON_STAND",
            "不明": "UNKNOWN",
            "未知": "UNKNOWN",
        }
    },
    "evidence": {
        "valid_values": {"CONFIRMED_STRIKE_WITH_REMAINS", "SYSTEM_WARNING", "ABNORMAL_NOISE_VIBRATION", "SUSPECTED_ONLY", "NO_ABNORMALITY", "UNKNOWN"},
        "mappings": {
            "残留": "CONFIRMED_STRIKE_WITH_REMAINS",
            "羽毛": "CONFIRMED_STRIKE_WITH_REMAINS",
            "血迹": "CONFIRMED_STRIKE_WITH_REMAINS",
            "确认撞击": "CONFIRMED_STRIKE_WITH_REMAINS",
            "告警": "SYSTEM_WARNING",
            "报警": "SYSTEM_WARNING",
            "ECAM": "SYSTEM_WARNING",
            "EICAS": "SYSTEM_WARNING",
            "异响": "ABNORMAL_NOISE_VIBRATION",
            "振动": "ABNORMAL_NOISE_VIBRATION",
            "震动": "ABNORMAL_NOISE_VIBRATION",
            "仅怀疑": "SUSPECTED_ONLY",
            "疑似": "SUSPECTED_ONLY",
            "无异常": "NO_ABNORMALITY",
            "正常": "NO_ABNORMALITY",
        }
    },
    "bird_info": {
        "valid_values": {"LARGE_BIRD", "FLOCK", "MEDIUM_SMALL_SINGLE", "UNKNOWN"},
        "mappings": {
            "大型鸟": "LARGE_BIRD",
            "大鸟": "LARGE_BIRD",
            "鸟群": "FLOCK",
            "群鸟": "FLOCK",
            "中小型": "MEDIUM_SMALL_SINGLE",
            "小型": "MEDIUM_SMALL_SINGLE",
            "单只": "MEDIUM_SMALL_SINGLE",
            "不明": "UNKNOWN",
            "未知": "UNKNOWN",
        }
    },
    "ops_impact": {
        "valid_values": {"RTO_OR_RTB", "BLOCKING_RUNWAY_OR_TAXIWAY", "REQUEST_MAINT_CHECK", "NO_OPS_IMPACT", "RUNWAY_CLOSED", "TAXIWAY_BLOCKED", "APRON_RESTRICTED", "MINOR_IMPACT", "NO_IMPACT", "UNKNOWN"},
        "mappings": {
            "中断起飞": "RTO_OR_RTB",
            "返航": "RTO_OR_RTB",
            "备降": "RTO_OR_RTB",
            "占用跑道": "BLOCKING_RUNWAY_OR_TAXIWAY",
            "占用滑行道": "BLOCKING_RUNWAY_OR_TAXIWAY",
            "阻塞跑道": "BLOCKING_RUNWAY_OR_TAXIWAY",
            "阻塞滑行道": "BLOCKING_RUNWAY_OR_TAXIWAY",
            "机务检查": "REQUEST_MAINT_CHECK",
            "请求检查": "REQUEST_MAINT_CHECK",
            "待检查": "REQUEST_MAINT_CHECK",
            "不影响运行": "NO_OPS_IMPACT",
            "无影响": "NO_OPS_IMPACT",
            "跑道关闭": "RUNWAY_CLOSED",
            "滑行道封闭": "TAXIWAY_BLOCKED",
            "机坪限制": "APRON_RESTRICTED",
            "轻微影响": "MINOR_IMPACT",
            "不影响": "NO_IMPACT",
            "不明": "UNKNOWN",
            "未知": "UNKNOWN",
        }
    },
}


def _normalize_enum_value(field_name: str, value: Any) -> Any:
    """统一的枚举值规范化函数"""
    if field_name not in ENUM_VALUE_MAPS:
        return value

    # 处理空值
    if value is None or value == "":
        return value

    config = ENUM_VALUE_MAPS[field_name]
    valid_values = config["valid_values"]
    mappings = config["mappings"]

    # 处理布尔值（related_event字段）
    if field_name == "related_event" and isinstance(value, bool):
        return "YES" if value else "NO"

    # 处理字符串值
    value_str = str(value).strip().upper()

    # 如果已经是有效值，直接返回
    if value_str in valid_values or value_str in {"NULL"}:
        return value_str if value_str != "NULL" else None

    # 尝试映射
    mapped = mappings.get(value_str)
    if mapped:
        return mapped

    # fod_size可能是自由文本描述，保留原值
    if field_name == "fod_size":
        return value

    return value


def _get_scenario_field_keys(scenario_type: Optional[str]) -> set[str]:
    """获取场景的所有字段key集合（包含通用字段）"""
    # 通用字段总是允许
    common_fields = {'flight_no', 'flight_no_display', 'position', 'position_display', 'report_time', 'reported_by'}

    if not scenario_type:
        return common_fields

    scenario = ScenarioRegistry.get(scenario_type)
    if not scenario:
        return common_fields

    # 收集场景特定字段
    scenario_fields = {
        field.get("key")
        for field in scenario.p1_fields + scenario.p2_fields
        if field.get("key")
    }

    return common_fields | scenario_fields


def _build_field_descriptions_for_llm(scenario_type: Optional[str]) -> str:
    """根据场景类型构建字段描述（用于LLM prompt）"""
    if not scenario_type:
        return "- position: 事发位置\n- flight_no: 航班号"

    scenario = ScenarioRegistry.get(scenario_type)
    if not scenario:
        return "- position: 事发位置\n- flight_no: 航班号"

    field_descriptions = []
    for field in scenario.p1_fields + scenario.p2_fields:
        key = field.get("key")
        if not key:
            continue

        label = field.get("label", key)
        field_type = field.get("type")

        # 枚举类型列出选项
        if field_type == "enum" and field.get("options"):
            option_strs = [
                f"{opt.get('value')}={opt.get('label', opt.get('value'))}"
                for opt in field.get("options", [])
            ]
            field_descriptions.append(f"- {key}: {label}（{', '.join(option_strs)}）")
        else:
            field_descriptions.append(f"- {key}: {label}")

    return "\n".join(field_descriptions)


def _build_llm_extract_prompt(scenario_type: Optional[str]) -> str:
    """根据场景类型动态构建LLM提取prompt"""
    field_descriptions = _build_field_descriptions_for_llm(scenario_type)

    return f"""你是一个机场应急响应系统的事件信息提取助手。

根据对话历史和当前用户输入，提取事件信息。输出 JSON 格式：

## 对话历史：
{{history}}

## 当前用户输入：
{{user_input}}

## 需要提取的字段（仅提取以下字段，不要提取其他字段）：
{field_descriptions}

## 智能提取规则：
1. 如果用户只输入纯数字（2-3位），且问题是关于位置的 → 识别为机位号
2. 如果用户输入航班号格式（2字母+3-4数字） → 识别为 flight_no
3. 如果用户回答"是/否/不知道"等，且没有明确信息 → 返回空 {{}}
4. **重要**：如果用户明确表示某个信息"不明"、"不清楚"、"不知道"，提取为 UNKNOWN（不要返回空）
5. 只提取明确的信息，不要猜测
6. **关键**：只能提取上述列出的字段，严禁提取其他场景的字段

## 输出格式：
{{"position": "...", "field1": "...", "field2": "...", ...}}

如果无法提取任何有效信息，返回 {{}}
"""


def _merge_patterns(scenario_type: str) -> Dict[str, Any]:
    """合并通用正则与场景正则（manifest regex）"""
    base = {k: v[:] if isinstance(v, list) else v for k, v in BASE_PATTERNS.items()}
    scenario = ScenarioRegistry.get(scenario_type) if scenario_type else None
    if scenario and scenario.regex_patterns:
        for key, items in scenario.regex_patterns.items():
            merged: List[Any] = []
            for item in items or []:
                pattern = item.get("pattern")
                value = item.get("value")
                if pattern:
                    merged.append((pattern, value))
            if merged:
                base[key] = merged
    return base


def extract_entities(text: str, scenario_type: Optional[str] = None) -> Dict[str, Any]:
    """从文本中提取实体（通用+场景 regex）"""
    entities: Dict[str, Any] = {}
    patterns = _merge_patterns(scenario_type or "")

    for pattern in patterns.get("position", []):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                prefix, suffix = match.group(1), match.group(2)
                entities["position"] = f"{prefix}{suffix}"
            else:
                entities["position"] = match.group(1)
            break

    if "position" not in entities:
        text_stripped = text.strip()
        if re.match(r"^\d{2,3}$", text_stripped):
            entities["position"] = text_stripped
        elif re.match(r"^(跑道|滑行道|机位)\s*\d+", text_stripped, re.IGNORECASE):
            match = re.match(r"^(跑道|滑行道|机位)\s*(\d+)", text_stripped, re.IGNORECASE)
            if match:
                entities["position"] = f"{match.group(1)}{match.group(2)}"
        else:
            match = re.search(r"(跑道|滑行道|机位|TWY|RWY)[_\s]?([A-Z]?\d+)", text, re.IGNORECASE)
            if match:
                entities["position"] = f"{match.group(1)}{match.group(2)}"
            else:
                match = re.search(r"\b(\d{2,3})\b", text)
                if match:
                    entities["position"] = match.group(1)

    for pattern, value in patterns.get("fluid_type", []):
        if re.search(pattern, text):
            entities["fluid_type"] = value
            break

    for key in ["event_type", "affected_part", "current_status", "crew_request"]:
        for pattern, value in patterns.get(key, []):
            if re.search(pattern, text):
                entities[key] = value
                break

    for pattern, value in patterns.get("engine_status", []):
        if re.search(pattern, text):
            entities["engine_status"] = value
            break

    for pattern, value in patterns.get("continuous", []):
        if re.search(pattern, text):
            entities["continuous"] = value
            break

    for pattern, value in patterns.get("leak_size", []):
        if re.search(pattern, text):
            entities["leak_size"] = value
            break

    for pattern in patterns.get("aircraft", []):
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            if value.startswith("B-"):
                continue
            elif value.isdigit():
                for cn_name, code in AIRLINE_CHINESE_TO_IATA.items():
                    if cn_name in text:
                        entities["flight_no_display"] = f"{cn_name}{value}"
                        entities["flight_no"] = f"{code}{value}"
                        break
            else:
                entities["flight_no_display"] = value
                entities["flight_no"] = value
            break

    handled_keys = {
        "position",
        "fluid_type",
        "event_type",
        "affected_part",
        "current_status",
        "crew_request",
        "engine_status",
        "continuous",
        "leak_size",
        "aircraft",
    }

    for key, items in patterns.items():
        if key in handled_keys or key in entities:
            continue
        if not isinstance(items, list):
            continue
        for pattern, value in items:
            if re.search(pattern, text, re.IGNORECASE):
                entities[key] = value
                break

    return entities


def extract_entities_llm(text: str, history: str = "", scenario_type: Optional[str] = None) -> Dict[str, Any]:
    """使用 LLM 提取实体（更灵活，根据场景类型动态构建prompt）"""
    try:
        llm = get_llm_client()
        # 使用动态构建的prompt
        prompt_template = _build_llm_extract_prompt(scenario_type)
        prompt = prompt_template.format(history=history, user_input=text)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        # 解析 JSON
        import json
        entities = json.loads(content)

        # 过滤：只保留当前场景的字段
        if scenario_type:
            allowed_fields = _get_scenario_field_keys(scenario_type)

            logger.info(f"场景类型: {scenario_type}")
            logger.info(f"允许的字段: {allowed_fields}")
            logger.info(f"LLM提取的字段: {set(entities.keys())}")

            filtered_entities = {k: v for k, v in entities.items() if k in allowed_fields}
            removed_fields = set(entities.keys()) - set(filtered_entities.keys())
            if removed_fields:
                logger.info(f"已过滤掉的字段: {removed_fields}")

            entities = filtered_entities

        # 统一规范化所有枚举值
        for field_name in list(entities.keys()):
            if entities[field_name] is not None:
                entities[field_name] = _normalize_enum_value(field_name, entities[field_name])

        # 清理 null 值
        return {k: v for k, v in entities.items() if v not in [None, "null", "NULL", ""]}

    except Exception:
        return {}


def extract_entities_hybrid(text: str, history: str = "", scenario_type: Optional[str] = None) -> Dict[str, Any]:
    """
    混合实体提取：先用正则，再用 LLM 补充

    策略：
    1. 快速路径：正则提取（处理格式固定的：航班号、位置）
    2. 灵活路径：LLM 提取（处理语义表达）
    """
    # 第一步：正则提取（快速、确定性）
    entities = extract_entities(text, scenario_type)
    logger.debug(f"[Hybrid Extract] 正则提取结果: {entities}")

    # 第二步：LLM 补充（处理模糊表达），传递场景类型
    llm_entities = extract_entities_llm(text, history, scenario_type)
    logger.debug(f"[Hybrid Extract] LLM提取结果: {llm_entities}")

    # 合并结果：LLM 结果补充正则结果（正则优先，LLM补充）
    # 修改策略：优先保留正则提取的结果，LLM只补充正则未提取到的字段
    for key, value in llm_entities.items():
        # 只在正则没有提取到该字段时，才使用LLM结果
        if key not in entities and value is not None and value != "null":
            entities[key] = value

    logger.debug(f"[Hybrid Extract] 合并后结果: {entities}")
    return entities


# 如果直接运行，测试提取效果
if __name__ == "__main__":
    test_inputs = [
        "501机位发现燃油泄漏，发动机运转中，持续滴漏，面积大概2平米",
        "A3滑行道有液压油漏",
        "CA1234航班在32号机位，发动机已关闭",
        "跑道01L发现不明油液",
        "CA2345，滑行道234，报告漏油",  # 测试多实体提取
    ]

    print("=" * 60)
    print("测试多实体提取")
    print("=" * 60)

    for inp in test_inputs:
        print(f"\n输入: {inp}")
        print(f"正则: {extract_entities(inp)}")
        print(f"混合: {extract_entities_hybrid(inp)}")
def _infer_required_fields(scenario: Any, incident: Dict[str, Any]) -> List[str]:
    """根据场景或已有字段推断必填字段列表，避免误用漏油字段。"""
    if scenario:
        return [
            field.get("key")
            for field in scenario.p1_fields
            if field.get("key") and field.get("required", True)
        ]
    # 无场景但已有鸟击字段时，按鸟击必填
    bird_keys = {"event_type", "affected_part", "current_status", "crew_request"}
    if bird_keys.intersection(incident.keys()):
        return ["flight_no", "position", "event_type", "affected_part", "current_status", "crew_request"]
    return ["fluid_type", "position", "engine_status", "continuous", "flight_no"]


def _select_scenario(current: str, detected: str) -> str:
    """根据优先级选择场景，避免已确认场景被降级。"""
    if not current:
        return detected
    if current == detected:
        return current

    current_scenario = ScenarioRegistry.get(current)
    detected_scenario = ScenarioRegistry.get(detected)
    cur_priority = current_scenario.metadata.get("priority", 100) if current_scenario else 100
    det_priority = detected_scenario.metadata.get("priority", 100) if detected_scenario else 100

    # 优先保留更高优先级（数值更小）的场景，避免从鸟击切回漏油
    if cur_priority <= det_priority:
        return current
    return detected
