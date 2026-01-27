"""
工具执行节点

职责：
1. 路由到具体工具
2. 执行工具
3. 更新状态
4. 返回观察结果
"""
import logging
import re
from datetime import datetime
from typing import Dict, Any, cast

from agent.state import AgentState, ActionStatus
from agent.exceptions import ToolExecutionError
from agent.retry import retry
from tools.registry import get_tool, ToolRegistry

logger = logging.getLogger(__name__)

def _build_return_state(state: AgentState, updates: Dict[str, Any]) -> Dict[str, Any]:
    """构建返回状态，确保关键字段被传递。

    LangGraph 0.2.x 使用 Dict[str, Any] 时不会自动合并状态，
    需要显式传递关键字段以确保下游节点能访问完整状态。
    """
    critical_fields = [
        "session_id",
        "scenario_type",
        "incident",
        "checklist",
        "messages",
        "risk_assessment",
        "spatial_analysis",
        "weather",
        "weather_impact",
        "mandatory_actions_done",
        "actions_taken",
        "notifications_sent",
        "fsm_state",
        "reference_flight",
        "flight_plan_table",
        "position_impact_analysis",
        "comprehensive_analysis",
        "flight_impact_prediction",
        "cleanup_time_estimate",
    ]

    result: Dict[str, Any] = {}
    for field in critical_fields:
        if field in state:
            result[field] = state[field]

    result.update(updates)
    return result


def tool_executor_node(state: AgentState) -> Dict[str, Any]:
    """
    工具执行节点

    执行 ReAct Agent 决定的工具，返回观察结果
    """
    action = state.get("current_action", "")
    action_input = state.get("current_action_input", {})
    session_id = state.get("session_id", "unknown")


    if not action:
        logger.warning(f"[{session_id}] 工具执行: 未指定工具")
        return _build_return_state(state, {
            "current_observation": "没有指定要执行的工具",
            "next_node": "reasoning",
        })

    # 获取工具
    tool = get_tool(action)
    if not tool:
        logger.warning(f"[{session_id}] 工具执行: 未找到工具 {action}")
        return _build_return_state(state, {
            "current_observation": f"未找到工具: {action}",
            "next_node": "reasoning",
        })
    
    # 规范化部分工具输入（兼容 ReAct 格式异常）
    if action == "get_aircraft_info":
        action_input = _normalize_flight_input(action_input)

    # 避免重复询问已收集字段
    if action == "ask_for_detail":
        requested = action_input.get("field", "")
        fields = [f.strip() for f in str(requested).split(",") if f.strip()]
        if fields:
            checklist = state.get("checklist", {})
            incident = state.get("incident", {})
            missing = [f for f in fields if not checklist.get(f) or incident.get(f) is None]
            if not missing:
                return _build_return_state(state, {
                    "current_observation": "目标字段已收集，跳过重复询问",
                    "next_node": "reasoning",
                })

    # 创建动作记录（提前，避免异常时未定义）
    action_record = {
        "action": action,
        "params": action_input,
        "status": ActionStatus.IN_PROGRESS.value,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # 执行工具
        start_time = datetime.now()
        logger.info(f"[{session_id}] 工具执行开始: {action}, 输入: {str(action_input)[:200]}")

        # 使用带验证的执行方法（如果工具支持）
        result = execute_tool_with_retry(
            tool,
            state,
            action_input,
            max_retries=getattr(tool, "max_retries", 2),
        )

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            f"[{session_id}] 工具执行成功: {action}, "
            f"耗时: {duration_ms:.1f}ms, "
            f"结果长度: {len(result.get('observation', ''))}"
        )

        # 更新动作记录
        action_record["status"] = ActionStatus.COMPLETED.value
        action_record["result"] = result.get("observation", "")
        
        # 合并工具返回的状态更新
        updates = {
            "current_observation": result.get("observation", "工具执行完成"),
            "actions_taken": state.get("actions_taken", []) + [action_record],
            "current_action": action,  # 保留action信息，用于检查是否需要用户输入
            "current_action_input": action_input,  # 保留action_input信息
            "next_node": "reasoning",
        }
        
        # 合并工具可能返回的其他状态更新
        for key in [
            "incident",
            "checklist",
            "risk_assessment",
            "spatial_analysis",
            "weather",
            "mandatory_actions_done",
            "notifications_sent",
            "messages",
            "final_report",
            "final_answer",
            "report_generated",
            "awaiting_supplemental_info",
            "supplemental_notes",
            "finalize_report",
            "supplemental_prompted",
            "comprehensive_analysis",
            "comprehensive_analysis_failed",
            "flight_impact_prediction",
            "position_impact_analysis",
            "weather_impact",
            "cleanup_time_estimate",
        ]:
            if key in result:
                if key == "messages":
                    # 消息需要追加
                    updates[key] = state.get(key, []) + result[key]
                elif key in ["incident", "checklist", "mandatory_actions_done", "spatial_analysis"]:
                    # 字典需要合并
                    updates[key] = {**state.get(key, {}), **result[key]}
                else:
                    updates[key] = result[key]

        if action == "get_weather":
            updates["weather_last_position"] = state.get("incident", {}).get("position")
            updates["weather_queried"] = True
        
        # 报告生成后等待用户确认，避免在确认前直接产出最终报告
        if result.get("report_generated"):
            updates["awaiting_user"] = True
            updates["next_node"] = "end"

        # 更新推理步骤中的 observation
        reasoning_steps = state.get("reasoning_steps", [])
        if reasoning_steps:
            reasoning_steps[-1]["observation"] = result.get("observation", "")
            updates["reasoning_steps"] = reasoning_steps

        if action == "analyze_spill_comprehensive":
            updates["comprehensive_analysis_failed"] = False

        # 【新增】如果计算出影响范围，自动调用航班影响预测
        if "spatial_analysis" in result and result["spatial_analysis"]:
            spatial = result["spatial_analysis"]
            if spatial.get("affected_stands") or spatial.get("affected_runways") or spatial.get("affected_taxiways"):
                # 检查是否已进行过航班影响预测
                if not state.get("flight_impact_prediction"):
                    try:
                        # 自动调用航班影响预测工具
                        predict_tool = get_tool("predict_flight_impact")
                        if predict_tool:
                            # 设置预测时间窗口为2小时
                            prediction_result = predict_tool.execute(state, {"time_window": 2})
                            if prediction_result and "flight_impact" in prediction_result:
                                # 添加预测结果到状态
                                updates["flight_impact_prediction"] = prediction_result["flight_impact"]
                                updates["actions_taken"] = updates.get("actions_taken", []) + [{
                                    "action": "predict_flight_impact",
                                    "params": {"time_window": 2},
                                    "status": ActionStatus.COMPLETED.value,
                                    "timestamp": datetime.now().isoformat(),
                                    "result": prediction_result.get("observation", ""),
                                }]

                                # 合并观察结果
                                current_obs = updates.get("current_observation", "")
                                prediction_obs = prediction_result.get("observation", "")
                                if prediction_obs:
                                    updates["current_observation"] = current_obs + "\n" + prediction_obs

                    except Exception as e:
                        # 航班影响预测失败不影响主流程，只记录日志
                        updates["actions_taken"] = updates.get("actions_taken", []) + [{
                            "action": "predict_flight_impact",
                            "params": {"time_window": 2},
                            "status": ActionStatus.FAILED.value,
                            "timestamp": datetime.now().isoformat(),
                            "result": f"预测失败: {str(e)}",
                        }]
                        current_obs = updates.get("current_observation", "")
                        updates["current_observation"] = current_obs + f"\n航班影响预测失败: {str(e)}"

        return _build_return_state(state, updates)
        
    except Exception as e:
        # 工具执行失败
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(
            f"[{session_id}] 工具执行失败: {action}, "
            f"耗时: {duration_ms:.1f}ms, "
            f"错误: {type(e).__name__}: {str(e)}",
            exc_info=True
        )

        action_record["status"] = ActionStatus.FAILED.value
        action_record["result"] = str(e)

        failure_updates = {
            "current_observation": f"工具执行失败: {str(e)}",
            "actions_taken": state.get("actions_taken", []) + [action_record],
            "next_node": "reasoning",
        }
        if action == "analyze_spill_comprehensive":
            failure_updates["comprehensive_analysis_failed"] = True

        return _build_return_state(state, failure_updates)


def _is_retryable_exception(exc: Exception) -> bool:
    return isinstance(exc, (TimeoutError, ConnectionError))


def execute_tool_with_retry(
    tool: Any,
    state: AgentState,
    action_input: Dict,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """带重试的工具执行"""
    tool_name = getattr(tool, "name", "unknown")
    max_attempts = max(1, max_retries)
    retryer = retry(
        max_attempts=max_attempts,
        delay=0.5,
        backoff=2.0,
        exceptions=(ToolExecutionError,),
    )

    def _call() -> Dict[str, Any]:
        try:
            if hasattr(tool, "execute_with_validation"):
                return cast(Dict[str, Any], tool.execute_with_validation(state, action_input))
            return cast(Dict[str, Any], tool.execute(state, action_input))
        except Exception as exc:
            raise ToolExecutionError(
                tool_name,
                str(exc),
                retryable=_is_retryable_exception(exc),
                cause=exc,
            ) from exc

    return retryer(_call)()


def _normalize_flight_input(action_input: Dict[str, Any]) -> Dict[str, Any]:
    """从混乱的输入中提取航班号"""
    if not isinstance(action_input, dict):
        return {}

    if action_input.get("flight_no"):
        return action_input

    raw = action_input.get("input", "")
    if isinstance(raw, dict) and raw.get("flight_no"):
        return {"flight_no": raw.get("flight_no")}

    if isinstance(raw, str):
        # 尝试从字符串中提取航班号
        match = re.search(r"\b([A-Z0-9]{2,3}\d{3,4})\b", raw, re.IGNORECASE)
        if match:
            return {"flight_no": match.group(1).upper()}
        # 兼容中文航司名称
        cn_match = re.search(r"(国航|东航|南航|海航|川航|厦航|深航|山航|昆航|顺丰|圆通|中货航)\s*(\d{3,4})", raw)
        if cn_match:
            return {"flight_no": f"{cn_match.group(1)}{cn_match.group(2)}"}
        # 兜底：包含数字的字符串直接使用
        if re.search(r"\d{3,4}", raw):
            return {"flight_no": raw.strip()}

    return action_input
