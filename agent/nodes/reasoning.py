"""
ReAct 推理节点

融合方案核心：
- LLM 主导推理，决定下一步动作
- 受 Checklist 约束
- 感知 FSM 验证结果
- 支持场景专属 Prompt
"""
import json
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from agent.state import AgentState, FSMState
from agent.prompts.builder import build_prompt
from scenarios.base import ScenarioRegistry
from config.llm_config import get_llm_client
from tools.registry import get_tools_description, ToolRegistry


class ParseError(Exception):
    """LLM 输出解析错误"""


class StructuredOutputParser:
    """结构化输出解析器（JSON）"""

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_start = text.find("{")
            json_end = text.rfind("}")
            if json_start != -1 and json_end != -1 and json_end > json_start:
                return json.loads(text[json_start:json_end + 1])
            raise

    @staticmethod
    def parse(
        text: str,
        allowed_actions: Optional[set] = None
    ) -> Tuple[str, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        解析 LLM JSON 输出

        返回: (thought, action, action_input, final_answer)
        """
        try:
            data = StructuredOutputParser._extract_json(text)
        except json.JSONDecodeError as exc:
            raise ParseError(f"输出不是合法 JSON: {exc}") from exc

        thought = str(data.get("thought", "")).strip()
        action = data.get("action")
        action_input = data.get("action_input")
        final_answer = data.get("final_answer")

        if not thought:
            raise ParseError("缺少 thought 字段")

        if not action and not final_answer:
            raise ParseError("必须提供 action 或 final_answer")

        if action:
            if not isinstance(action, str):
                raise ParseError("action 必须为字符串")
            if allowed_actions is not None and action not in allowed_actions:
                raise ParseError(f"action 不在可用工具列表: {action}")

            if action_input is None:
                action_input = {}
            elif not isinstance(action_input, dict):
                action_input = {"input": action_input}

        if final_answer is not None and not isinstance(final_answer, str):
            raise ParseError("final_answer 必须为字符串")

        return thought, action, action_input, final_answer


def _is_waiting_for_user(final_answer: str) -> bool:
    """判断是否为等待用户回复的占位回答"""
    if not final_answer:
        return False
    return "等待用户" in final_answer or "等待回复" in final_answer


def check_immediate_triggers(state: AgentState) -> Optional[Dict[str, Any]]:
    """
    检查是否需要立即触发强制动作

    融合设计：
    - 强制动作规则来源于场景配置
    - 在 ReAct 推理前检查
    """
    from agent.nodes.fsm_validator import get_fsm_validator

    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    errors, pending_actions = validator.check_mandatory_actions(state)
    if not pending_actions:
        return None

    pending = pending_actions[0]
    reason = errors[0] if errors else f"需要执行强制动作: {pending.get('name', pending['action'])}"

    return {
        "forced_action": pending["action"],
        "forced_input": pending.get("params", {}),
        "reason": reason,
    }


def check_auto_weather_trigger(state: AgentState) -> Optional[Dict[str, Any]]:
    """检测是否需要触发自动气象查询"""
    def _normalize_weather_position(value: Optional[str]) -> str:
        if not value:
            return ""
        return re.sub(r"^(RUNWAY|RWY|跑道)\\s*", "", value.strip().upper())

    incident = state.get("incident", {})
    position = incident.get("position")
    if not position:
        return None
    if state.get("weather"):
        return None
    if state.get("current_action") == "get_weather":
        return None
    if state.get("weather_queried"):
        last_position = state.get("weather_last_position", "")
        if _normalize_weather_position(last_position) == _normalize_weather_position(position):
            return None
    return {
        "forced_action": "get_weather",
        "forced_input": {"location": position},
        "reason": "自动查询气象信息",
    }


def _should_prompt_supplemental(state: AgentState) -> bool:
    if state.get("awaiting_user") or state.get("awaiting_supplemental_info"):
        return False
    if state.get("supplemental_prompted") or state.get("report_generated"):
        return False

    scenario_type = state.get("scenario_type", "oil_spill")
    scenario = ScenarioRegistry.get(scenario_type)
    checklist = state.get("checklist", {})

    if scenario:
        p1_fields = [f.get("key") for f in scenario.p1_fields if f.get("key")]
        if any(not checklist.get(f) for f in p1_fields):
            return False
        if scenario.risk_required:
            mandatory = state.get("mandatory_actions_done", {})
            if not mandatory.get("risk_assessed"):
                return False
    else:
        required = ["fluid_type", "position", "engine_status", "continuous"]
        if any(not checklist.get(f) for f in required):
            return False

    return True


def _should_run_comprehensive(state: AgentState) -> bool:
    if state.get("awaiting_user") or state.get("awaiting_supplemental_info"):
        return False
    if state.get("report_generated"):
        return False
    if state.get("comprehensive_analysis"):
        return False
    actions = state.get("actions_taken", [])
    if any(action.get("action") == "analyze_spill_comprehensive" for action in actions):
        return False
    if state.get("comprehensive_analysis_failed"):
        return False
    if state.get("scenario_type") != "oil_spill":
        return False

    scenario = ScenarioRegistry.get("oil_spill")
    checklist = state.get("checklist", {})
    if scenario:
        p1_fields = [f.get("key") for f in scenario.p1_fields if f.get("key")]
        if any(not checklist.get(f) for f in p1_fields):
            return False
        if scenario.risk_required:
            mandatory = state.get("mandatory_actions_done", {})
            if not mandatory.get("risk_assessed"):
                return False
    return True


def build_context_summary(state: AgentState) -> str:
    """构建上下文摘要"""
    parts = []

    # 航班信息（如果有）
    incident = state.get("incident", {})
    if incident.get("airline") or incident.get("flight_no"):
        flight_parts = []
        if incident.get("flight_no_display"):
            flight_parts.append(f"航班号: {incident['flight_no_display']}")
        elif incident.get("flight_no"):
            flight_parts.append(f"航班号: {incident['flight_no']}")
        if incident.get("airline"):
            flight_parts.append(f"航司: {incident['airline']}")
        if incident.get("stand"):
            flight_parts.append(f"停机位: {incident['stand']}")
        if incident.get("runway"):
            flight_parts.append(f"跑道: {incident['runway']}")
        if incident.get("flight_type"):
            flight_parts.append(f"航班类型: {'到达' if incident['flight_type'] == 'A' else '出发' if incident['flight_type'] == 'D' else incident['flight_type']}")
        if flight_parts:
            parts.append("航班信息: " + ", ".join(flight_parts))

    # 事件信息
    if incident:
        info_parts = []
        if incident.get("position_display") or incident.get("position"):
            info_parts.append(f"位置: {incident.get('position_display') or incident.get('position')}")
        if incident.get("fluid_type"):
            info_parts.append(f"油液类型: {incident['fluid_type']}")
        if incident.get("engine_status"):
            info_parts.append(f"发动机: {incident['engine_status']}")
        if incident.get("continuous") is not None:
            info_parts.append(f"持续滴漏: {'是' if incident['continuous'] else '否'}")
        if incident.get("leak_size"):
            info_parts.append(f"面积: {incident['leak_size']}")
        if info_parts:
            parts.append("事件信息: " + ", ".join(info_parts))

    # 气象信息
    weather = state.get("weather", {})
    if weather:
        weather_parts = []
        if weather.get("location"):
            weather_parts.append(f"观测点: {weather['location']}")
        if weather.get("temperature") is not None:
            weather_parts.append(f"温度: {weather['temperature']:.1f}°C")
        if weather.get("wind_speed") is not None:
            wind_dir_str = f"{weather.get('wind_direction'):.0f}°" if weather.get('wind_direction') else "未知"
            weather_parts.append(f"风: {wind_dir_str} {weather['wind_speed']:.1f}m/s")
        if weather.get("qnh") is not None:
            weather_parts.append(f"气压: {weather['qnh']:.0f}hPa")
        if weather.get("visibility") is not None:
            vis_km = weather['visibility'] / 1000
            weather_parts.append(f"能见度: {vis_km:.1f}km")
        if weather_parts:
            parts.append("气象条件: " + ", ".join(weather_parts))

    # Checklist 状态
    checklist = state.get("checklist", {})
    missing = [k for k, v in checklist.items() if not v]
    if missing:
        parts.append(f"待收集信息: {', '.join(missing)}")

    # 风险评估结果
    risk = state.get("risk_assessment", {})
    if risk.get("level"):
        parts.append(f"风险等级: {risk['level']}")

    # 空间分析结果（拓扑分析）
    spatial = state.get("spatial_analysis", {})
    impact_zone = incident.get("impact_zone", {})

    # 显示位置详情
    if spatial.get("stand_info"):
        stand = spatial["stand_info"]
        parts.append(f"停机位位置: {stand.get('id')}({stand.get('lat'):.5f}, {stand.get('lon'):.5f})")
        if stand.get("adjacent_taxiways"):
            parts.append(f"相邻滑行道: {', '.join(stand['adjacent_taxiways'])}")
        if stand.get("nearest_runway"):
            parts.append(f"最近跑道: {stand['nearest_runway']}")

    # 显示影响范围
    if impact_zone.get("affected_taxiways") or impact_zone.get("affected_runways"):
        affected_parts = []
        if impact_zone.get("affected_taxiways"):
            affected_parts.append(f"滑行道{len(impact_zone['affected_taxiways'])}处")
        if impact_zone.get("affected_runways"):
            affected_parts.append(f"跑道{len(impact_zone['affected_runways'])}条")
        if impact_zone.get("affected_stands"):
            affected_parts.append(f"机位{len(impact_zone['affected_stands'])}个")
        if affected_parts:
            parts.append(f"影响范围: {'、'.join(affected_parts)}")
        if impact_zone.get("anchor_node"):
            parts.append(f"隔离锚点: {impact_zone['anchor_node']}")

    # FSM 验证错误
    errors = state.get("fsm_validation_errors", [])
    if errors:
        parts.append(f"需要处理的问题: {'; '.join(errors)}")

    # 语义验证提示
    semantic_validation = state.get("semantic_validation", {})
    if semantic_validation:
        semantic_parts = []
        semantic_issues = semantic_validation.get("semantic_issues") or []
        missing_fields = semantic_validation.get("missing_fields") or []
        low_confidence = semantic_validation.get("low_confidence_fields") or []
        if semantic_issues:
            semantic_parts.append(f"语义矛盾: {'; '.join(semantic_issues)}")
        if missing_fields:
            semantic_parts.append(f"缺失字段: {', '.join(missing_fields)}")
        if low_confidence:
            low_fields = [item.get("field", "") for item in low_confidence if item.get("field")]
            if low_fields:
                semantic_parts.append(f"低置信度字段: {', '.join(low_fields)}")
        if semantic_parts:
            parts.append("语义验证: " + "；".join(semantic_parts))

    # 已执行动作
    actions = state.get("actions_taken", [])
    if actions:
        action_names = [a.get("action", "") for a in actions[-3:]]  # 最近3个
        parts.append(f"已执行动作: {', '.join(action_names)}")

    return "\n".join(parts) if parts else "暂无已知信息"


def reasoning_node(state: AgentState) -> Dict[str, Any]:
    """
    ReAct 推理节点
    
    融合设计：
    1. 先检查强制触发条件
    2. 构建包含约束信息的 Prompt
    3. LLM 推理决定下一步
    4. 解析输出
    """
    # 检查迭代次数
    iteration = state.get("iteration_count", 0) + 1

    if state.get("finalize_report"):
        return {
            "current_thought": "收到补充信息，重新生成最终报告",
            "next_node": "output_generator",
            "iteration_count": iteration,
            "finalize_report": False,
            "reasoning_steps": state.get("reasoning_steps", []) + [{
                "step": iteration,
                "thought": "补充信息已记录，生成最终报告",
                "action": "output_generator",
                "action_input": {},
                "timestamp": datetime.now().isoformat(),
            }],
        }

    # 检查强制触发
    forced = check_immediate_triggers(state)
    if forced:
        return {
            "current_thought": forced["reason"],
            "current_action": forced["forced_action"],
            "current_action_input": forced["forced_input"],
            "next_node": "tool_executor",
            "iteration_count": iteration,
            "reasoning_steps": state.get("reasoning_steps", []) + [{
                "step": iteration,
                "thought": f"[强制触发] {forced['reason']}",
                "action": forced["forced_action"],
                "action_input": forced["forced_input"],
                "timestamp": datetime.now().isoformat(),
            }],
        }

    auto_weather = check_auto_weather_trigger(state)
    if auto_weather:
        return {
            "current_thought": auto_weather["reason"],
            "current_action": auto_weather["forced_action"],
            "current_action_input": auto_weather["forced_input"],
            "next_node": "tool_executor",
            "iteration_count": iteration,
            "reasoning_steps": state.get("reasoning_steps", []) + [{
                "step": iteration,
                "thought": f"[自动触发] {auto_weather['reason']}",
                "action": auto_weather["forced_action"],
                "action_input": auto_weather["forced_input"],
                "timestamp": datetime.now().isoformat(),
            }],
        }

    # 优先处理语义验证的补问需求
    semantic_validation = state.get("semantic_validation", {})
    if semantic_validation and not state.get("awaiting_user"):
        if (semantic_validation.get("semantic_issues") or
                semantic_validation.get("missing_fields") or
                semantic_validation.get("low_confidence_fields")):
            from agent.nodes.dialogue_strategy import generate_next_question

            question = generate_next_question(state, semantic_validation)
            reasoning_steps = state.get("reasoning_steps", [])
            new_step = {
                "step": iteration,
                "thought": "语义验证发现缺失或不确定信息，发起追问",
                "action": "ask_for_detail",
                "action_input": semantic_validation,
                "timestamp": datetime.now().isoformat(),
            }
            return {
                "current_thought": "需要补充关键信息",
                "messages": [{"role": "assistant", "content": question}],
                "awaiting_user": True,
                "next_node": "end",
                "iteration_count": iteration,
                "reasoning_steps": reasoning_steps + [new_step],
            }

    if _should_run_comprehensive(state):
        reasoning_steps = state.get("reasoning_steps", [])
        new_step = {
            "step": iteration,
            "thought": "P1与风险评估已完成，调用综合分析工具",
            "action": "analyze_spill_comprehensive",
            "action_input": {},
            "timestamp": datetime.now().isoformat(),
        }
        return {
            "current_thought": "执行综合分析",
            "current_action": "analyze_spill_comprehensive",
            "current_action_input": {},
            "next_node": "tool_executor",
            "iteration_count": iteration,
            "reasoning_steps": reasoning_steps + [new_step],
        }

    if _should_prompt_supplemental(state):
        incident = state.get("incident", {})
        flight_no = incident.get("flight_no_display") or incident.get("flight_no") or ""
        prompt = "处置流程已完成。若有补充信息请直接说明；如无请回复“完毕”或“结束”。"
        if flight_no:
            prompt = f"{flight_no}，{prompt}"
        reasoning_steps = state.get("reasoning_steps", [])
        new_step = {
            "step": iteration,
            "thought": "P1信息已完成，发起补充信息确认",
            "action": "ask_for_detail",
            "action_input": {"field": "supplemental_notes"},
            "timestamp": datetime.now().isoformat(),
        }
        return {
            "current_thought": "需要确认补充信息",
            "messages": [{"role": "assistant", "content": prompt}],
            "awaiting_user": True,
            "awaiting_supplemental_info": True,
            "supplemental_prompted": True,
            "next_node": "end",
            "iteration_count": iteration,
            "reasoning_steps": reasoning_steps + [new_step],
        }
    
    # 构建上下文
    context = build_context_summary(state)

    # 获取对话历史
    messages = state.get("messages", [])

    # 获取推理历史
    reasoning_steps = state.get("reasoning_steps", [])

    # 获取工具描述
    tools_desc = get_tools_description(state.get("scenario_type", "oil_spill"))

    # 获取 Checklist 状态
    checklist = state.get("checklist", {})

    # 获取 FSM 验证错误
    fsm_errors = state.get("fsm_validation_errors", [])

    # 构建 Prompt（使用场景专属配置）
    prompt = build_prompt(
        state=state,
        context=context,
        messages=messages,
        reasoning_history=reasoning_steps,
        tools_description=tools_desc,
        checklist=checklist,
        fsm_errors=fsm_errors,
    )
    
    # 调用 LLM
    try:
        llm = get_llm_client()
        response = llm.invoke(prompt)
        llm_output = response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        return {
            "error": f"LLM 调用失败: {str(e)}",
            "next_node": "end",
        }
    
    # 解析输出
    allowed_actions = set(ToolRegistry.get_all().keys())
    try:
        thought, action, action_input, final_answer = StructuredOutputParser.parse(
            llm_output, allowed_actions
        )
    except ParseError as parse_err:
        # 失败后尝试一次纠错
        retry_prompt = (
            f"{prompt}\n\n"
            f"## 输出纠错\n{parse_err}\n"
            "请只输出合法 JSON，且字段包含 thought，并提供 action 或 final_answer。"
        )
        try:
            llm = get_llm_client()
            retry_response = llm.invoke(retry_prompt)
            retry_output = (
                retry_response.content
                if hasattr(retry_response, 'content')
                else str(retry_response)
            )
            thought, action, action_input, final_answer = StructuredOutputParser.parse(
                retry_output, allowed_actions
            )
        except Exception as retry_exc:
            return {
                "current_thought": "无法解析 LLM 输出",
                "error": f"LLM 输出解析失败: {retry_exc}",
                "next_node": "end",
            }
    
    # 记录推理步骤
    new_step = {
        "step": iteration,
        "thought": thought,
        "action": action,
        "action_input": action_input,
        "timestamp": datetime.now().isoformat(),
    }
    
    # 如果有最终答案（LLM 认为任务完成）
    # 注意：不在这里设置 final_answer，而是让 output_generator 生成完整的检查单
    if final_answer:
        if _is_waiting_for_user(final_answer):
            return {
                "current_thought": thought,
                "final_answer": final_answer,
                "is_complete": False,
                "awaiting_user": True,
                "next_node": "end",
                "iteration_count": iteration,
                "reasoning_steps": reasoning_steps + [new_step],
            }
        return {
            "current_thought": thought,
            # 不设置 final_answer，让 output_generator 生成完整的检查单报告
            # "final_answer": final_answer,  # 删除这行，避免用简短回复覆盖完整检查单
            "is_complete": False,  # 还未真正完成，需要 output_generator 生成报告
            "next_node": "output_generator",  # 直接进入报告生成节点
            "iteration_count": iteration,
            "reasoning_steps": reasoning_steps + [new_step],
        }
    
    # 如果有动作
    if action:
        return {
            "current_thought": thought,
            "current_action": action,
            "current_action_input": action_input or {},
            "next_node": "tool_executor",
            "iteration_count": iteration,
            "reasoning_steps": reasoning_steps + [new_step],
        }
    
    # 没有动作也没有最终答案，可能是格式问题
    return {
        "current_thought": thought or "无法解析 LLM 输出",
        "error": "LLM 输出格式不正确",
        "next_node": "reasoning",  # 重试
        "iteration_count": iteration,
        "reasoning_steps": reasoning_steps + [new_step],
    }
