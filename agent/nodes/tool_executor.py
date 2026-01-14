"""
工具执行节点

职责：
1. 路由到具体工具
2. 执行工具
3. 更新状态
4. 返回观察结果
"""
from typing import Dict, Any
import re
from datetime import datetime

from agent.state import AgentState, ActionStatus
from tools.registry import get_tool, ToolRegistry


def tool_executor_node(state: AgentState) -> Dict[str, Any]:
    """
    工具执行节点
    
    执行 ReAct Agent 决定的工具，返回观察结果
    """
    action = state.get("current_action", "")
    action_input = state.get("current_action_input", {})

    if not action:
        return {
            "current_observation": "没有指定要执行的工具",
            "next_node": "reasoning",
        }
    
    # 获取工具
    tool = get_tool(action)
    if not tool:
        return {
            "current_observation": f"未找到工具: {action}",
            "next_node": "reasoning",
        }
    
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
                return {
                    "current_observation": "目标字段已收集，跳过重复询问",
                    "next_node": "reasoning",
                }

    # 创建动作记录（提前，避免异常时未定义）
    action_record = {
        "action": action,
        "params": action_input,
        "status": ActionStatus.IN_PROGRESS.value,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # 执行工具
        result = tool.execute(state, action_input)
        
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
        ]:
            if key in result:
                if key == "messages":
                    # 消息需要追加
                    updates[key] = state.get(key, []) + result[key]
                elif key in ["incident", "checklist", "mandatory_actions_done"]:
                    # 字典需要合并
                    updates[key] = {**state.get(key, {}), **result[key]}
                else:
                    updates[key] = result[key]

        if action == "get_weather":
            updates["weather_last_position"] = state.get("incident", {}).get("position")
            updates["weather_queried"] = True
        
        # 报告生成后等待用户确认，避免继续推理导致重复询问
        if result.get("report_generated"):
            if action == "generate_report":
                from agent.nodes.output_generator import output_generator_node

                draft_state = {**state, **updates}
                draft = output_generator_node(draft_state)
                updates["final_report"] = draft.get("final_report", {})
                updates["final_answer"] = draft.get("final_answer", "")
                updates["is_complete"] = False
                updates["awaiting_user"] = True
                updates["next_node"] = "end"
                updates["fsm_state"] = state.get("fsm_state")
            else:
                updates["awaiting_user"] = True
                updates["next_node"] = "end"

        # 更新推理步骤中的 observation
        reasoning_steps = state.get("reasoning_steps", [])
        if reasoning_steps:
            reasoning_steps[-1]["observation"] = result.get("observation", "")
            updates["reasoning_steps"] = reasoning_steps

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

        return updates
        
    except Exception as e:
        # 工具执行失败
        action_record["status"] = ActionStatus.FAILED.value
        action_record["result"] = str(e)
        
        return {
            "current_observation": f"工具执行失败: {str(e)}",
            "actions_taken": state.get("actions_taken", []) + [action_record],
            "next_node": "reasoning",
        }


def execute_tool_with_retry(tool, state: AgentState, action_input: Dict, max_retries: int = 2) -> Dict[str, Any]:
    """带重试的工具执行"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return tool.execute(state, action_input)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                continue
    
    raise last_error


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
