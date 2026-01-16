#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
机场机坪特情应急响应 Agent - 完整交互式终端

使用 LangGraph + LLM 的完整流程：
- ReAct 推理循环（调用大模型）
- FSM 状态验证
- 工具执行（规则引擎、图算法）
- 多轮对话支持
- LangSmith 追踪

运行方式:
    python apps/run_agent.py

环境配置:
    复制 .env.example 为 .env 并配置 LLM_API_KEY
    配置 LANGCHAIN_API_KEY 启用追踪
"""
import sys
import os
import re
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 改进的输入处理（使用标准 input，prompt_toolkit 可选）
# 如果需要更好的编辑体验，可以安装: pip install prompt_toolkit
PROMPT_TOOLKIT_AVAILABLE = False  # 设为 True 并安装 prompt_toolkit 以启用增强输入

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 启用 LangSmith 追踪（在导入其他模块之前）
from config.settings import settings
if settings.LANGCHAIN_TRACING_V2:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or "airport-agent"


# ============================================================
# 输出函数（无颜色无emoji）
# ============================================================

def print_header(text: str):
    print(f"\n{'='*65}")
    print(f" {text}")
    print(f"{'='*65}\n")


def print_subheader(text: str):
    print(f"\n--- {text} ---")


def print_agent(text: str):
    print(f"机坪管制: {text}")


def print_thought(text: str):
    print(f"  [思考] {text}")


def print_action(action: str, inputs: Dict = None):
    inputs_str = ""
    if inputs:
        display = inputs
        if isinstance(inputs, dict):
            display = dict(inputs)
            if "input" in display and isinstance(display["input"], str):
                trimmed = display["input"].replace("\n", " ").strip()
                if len(trimmed) > 200:
                    trimmed = trimmed[:200] + "..."
                display["input"] = trimmed
        inputs_str = f" -> {display}"
    print(f"  [执行] {action}{inputs_str}")


def print_observation(text: str):
    print(f"  [观察] {text}")


def print_fsm(state: str, transition: str = None):
    if transition:
        print(f"  [FSM] {transition} -> {state}")
    else:
        print(f"  [FSM] 状态: {state}")


def print_warning(text: str):
    print(f"  [警告] {text}")


def print_success(text: str):
    print(f"  [完成] {text}")


def print_info(text: str):
    print(f"  [信息] {text}")


def print_dim(text: str):
    print(f"  {text}")


def _load_radiotelephony_rules() -> Dict[str, Any]:
    rules_path = os.path.join(PROJECT_ROOT, "data", "raw", "Radiotelephony_ATC.json")
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        print_warning(f"读数规则文件格式错误: {exc}")
        return {}

    return {
        "digits": data.get("digits", {}),
        "letters": data.get("letters", {}),
        "terms": data.get("terms", {}),
    }


_RADIOTELEPHONY_RULES = _load_radiotelephony_rules()
_CONTROL_CALLSIGN = _RADIOTELEPHONY_RULES.get("control_callsign", "天府机坪")


def _extract_flight_callsign(text: str) -> str:
    match = re.search(r"\b([A-Z0-9]{2,3}\d{3,4})\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match = re.search(
        r"(国航|东航|南航|海航|川航|厦航|深航|山航|昆航|顺丰|圆通|中货航)\s*(?:[A-Z0-9]{2,3})?\s*(\d{3,4})",
        text,
    )
    if match:
        return f"{match.group(1)}{match.group(2)}"

    return ""


def _enforce_preamble_format(text: str, is_first_contact: bool) -> str:
    rules = _RADIOTELEPHONY_RULES
    if not rules or not rules.get("preamble"):
        return text

    normalized = text.strip()
    if not normalized:
        return normalized

    if _CONTROL_CALLSIGN and _CONTROL_CALLSIGN not in normalized:
        normalized = f"{_CONTROL_CALLSIGN} {normalized}"

    if is_first_contact:
        callsign = _extract_flight_callsign(normalized)
        if callsign and callsign not in normalized:
            normalized = f"{_CONTROL_CALLSIGN} {callsign} {normalized.replace(_CONTROL_CALLSIGN, '').strip()}"

    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized


def _strip_leading_callsigns(text: str, callsign: str) -> str:
    cleaned = text.strip()
    for token in [callsign, _CONTROL_CALLSIGN]:
        if token:
            cleaned = re.sub(rf"^(?:{re.escape(token)}[，,\\s]*)", "", cleaned)
    return cleaned.strip()


def format_control_reply(text: str, state: Dict[str, Any], is_first_contact: bool) -> str:
    rules = _RADIOTELEPHONY_RULES
    if not rules or not rules.get("preamble"):
        return text

    callsign = ""
    incident = state.get("incident", {}) if state else {}
    if incident:
        callsign = incident.get("flight_no_display") or incident.get("flight_no") or ""

    if not callsign:
        callsign = _extract_flight_callsign(text)

    if not callsign:
        return text

    content = _strip_leading_callsigns(text, callsign)
    if is_first_contact and _CONTROL_CALLSIGN:
        return f"{callsign} {_CONTROL_CALLSIGN} {content}".strip()
    return f"{callsign} {content}".strip()


def _spell_digits(number_text: str, digits_map: Dict[str, str]) -> str:
    return "".join(digits_map.get(ch, ch) for ch in number_text)


def _spell_letters(letter_text: str, letters_map: Dict[str, str]) -> str:
    spelled = []
    for ch in letter_text:
        upper = ch.upper()
        spelled.append(letters_map.get(upper, ch))
    return " ".join(spelled).strip()


def format_radiotelephony_readout(text: str) -> Optional[str]:
    """根据规则把输入转成航空读法（用于展示/播报与解析）"""
    rules = _RADIOTELEPHONY_RULES
    if not rules:
        return None

    terms = rules.get("terms", {})
    digits_map = rules.get("digits", {})
    letters_map = rules.get("letters", {})
    if not (terms and digits_map):
        return None

    result = text
    for term in sorted(terms.keys(), key=len, reverse=True):
        pattern = rf"{re.escape(term)}\s*([A-Za-z]+)?\s*(\d+)"

        def _replace(match: re.Match) -> str:
            letters_part = match.group(1) or ""
            digits_part = match.group(2)
            spoken_letters = _spell_letters(letters_part, letters_map) if letters_part else ""
            spoken_digits = _spell_digits(digits_part, digits_map)

            spoken = terms.get(term, term)
            if spoken_letters:
                spoken = f"{spoken} {spoken_letters}"
            return f"{spoken} {spoken_digits}".strip()

        result = re.sub(pattern, _replace, result)

    return result if result != text else None


def apply_readout_for_processing(text: str, is_first_contact: bool) -> str:
    normalized = _enforce_preamble_format(text, is_first_contact)
    if normalized != text:
        print_info(f"通话规范化: {normalized}")

    readout = format_radiotelephony_readout(normalized)
    if readout and readout != normalized:
        print_info(f"读法: {readout}")
        return readout
    return normalized


def get_user_input(prompt: str = "机长") -> str:
    """获取用户输入"""
    try:
        user_input = input(f"\n{prompt}: ")
        return user_input.strip()
    except (KeyboardInterrupt, EOFError):
        print("\n")
        return "exit"


# ============================================================
# 状态显示
# ============================================================

def print_checklist(checklist: Dict[str, bool]):
    """打印 Checklist 状态"""
    print(f"\n信息收集 Checklist:")
    field_names = {
        "fluid_type": "油液类型",
        "continuous": "持续泄漏",
        "engine_status": "发动机状态",
        "position": "事发位置",
        "leak_size": "泄漏面积",
    }
    for field, collected in checklist.items():
        name = field_names.get(field, field)
        status = "[v]" if collected else "[x]"
        print(f"  {status} {name}")


def print_risk_assessment(risk: Dict[str, Any]):
    """打印风险评估结果"""
    if not risk or not risk.get("level"):
        return

    level = risk.get("level", "UNKNOWN")
    score = risk.get("score", 0)

    print(f"\n风险评估:")
    print(f"  等级: {level} ({score}/100)")

    if risk.get("factors"):
        print(f"  因素: {', '.join(risk['factors'])}")

    if risk.get("immediate_actions"):
        print(f"  立即行动:")
        for action in risk["immediate_actions"]:
            print(f"    - {action}")


def print_spatial_analysis(spatial: Dict[str, Any]):
    """打印空间分析结果"""
    if not spatial or not spatial.get("isolated_nodes"):
        return

    print(f"\n影响范围:")
    if spatial.get("isolated_nodes"):
        print(f"  隔离区域: {', '.join(spatial['isolated_nodes'])}")
    if spatial.get("affected_taxiways"):
        print(f"  受影响滑行道: {', '.join(spatial['affected_taxiways'])}")
    if spatial.get("affected_runways"):
        print(f"  受影响跑道: {', '.join(spatial['affected_runways'])}")


def print_flight_impact_prediction(flight_impact: Dict[str, Any]):
    """打印航班影响预测结果"""
    if not flight_impact:
        return

    print(f"\n航班影响预测:")

    stats = flight_impact.get("statistics", {})
    if stats:
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)
        print(f"  受影响航班: {total} 架次")
        print(f"  平均延误: {avg_delay:.1f} 分钟")

        # 严重程度分布
        severity = stats.get("severity_distribution", {})
        if severity:
            high = severity.get("high", 0)
            medium = severity.get("medium", 0)
            low = severity.get("low", 0)
            if high or medium or low:
                print(f"  影响分布: 严重 {high}, 中等 {medium}, 轻微 {low}")

    # 受影响航班列表
    flights = flight_impact.get("affected_flights", [])
    if flights:
        print(f"\n  受影响航班列表（前5个）:")
        for i, flight in enumerate(flights[:5], 1):
            callsign = flight.get("callsign", "UNKNOWN")
            delay = flight.get("estimated_delay_minutes", 0)
            reason = flight.get("delay_reason", "")
            print(f"    {i}. {callsign}: 延误 {delay} 分钟 ({reason})")


def print_state_summary(state: Dict[str, Any]):
    """打印状态摘要"""
    print_subheader("当前状态摘要")

    # FSM 状态
    fsm_state = state.get("fsm_state", "INIT")
    print_fsm(fsm_state)

    # Checklist
    print_checklist(state.get("checklist", {}))

    # 风险评估
    print_risk_assessment(state.get("risk_assessment", {}))

    # 空间分析
    print_spatial_analysis(state.get("spatial_analysis", {}))

    # 航班影响预测
    print_flight_impact_prediction(state.get("flight_impact_prediction", {}))

    # 迭代次数
    iteration = state.get("iteration_count", 0)
    print(f"\n  迭代次数: {iteration}")


# ============================================================
# 用户回答解析
# ============================================================

# 导入 input_parser 中的混合实体提取函数
from agent.nodes.input_parser import extract_entities_hybrid, build_history_context


def extract_all_entities(text: str, history: str = "") -> Dict[str, Any]:
    """使用 input_parser 中的混合实体提取函数"""
    return extract_entities_hybrid(text, history)


def parse_simple_yes_no(text: str) -> Optional[bool]:
    """解析简单的是/否回答"""
    text = text.strip().lower()
    if text in ["是", "是的", "对", "yes", "y", "有", "在", "还在", "确定", "没错"]:
        return True
    elif text in ["否", "不", "没有", "no", "n", "不是", "没", "无"]:
        return False
    return None


def is_affirmative(text: str) -> bool:
    """检查文本是否是肯定回答（用于确认问题）"""
    text = text.strip().lower()
    return text in ["是", "是的", "对", "yes", "y", "确定", "没错", "对的", "正确", "sure"]


def is_negative(text: str) -> bool:
    """检查文本是否是否定回答"""
    text = text.strip().lower()
    return text in ["否", "不", "不是", "no", "n", "错了", "不对", "不对"]


def is_skip_or_unknown(text: str) -> bool:
    """检查文本是否是跳过/不确定回答"""
    text = text.strip().lower()
    skip_patterns = [
        "不确定", "不知道", "暂不确定", "后续补充", "待确认",
        "跳过", "跳过这个", "skip", "unknown", "unsure",
        "这个不重要", "先继续", "后面再说", "待定",
    ]
    return any(pattern in text for pattern in skip_patterns)


def is_completeness_question(text: str) -> bool:
    """检查是否是在问信息是否收集完整"""
    text = text.strip().lower()
    patterns = [
        "收集完了吗", "信息齐了吗", "可以了吗", "还有问题吗",
        "还有要问的吗", "可以生成报告了吗", "结束了吗",
        "complete", "enough", "sufficient",
    ]
    return any(pattern in text for pattern in patterns)


# ============================================================
# Agent 运行器 (使用 LangGraph)
# ============================================================

class AgentRunner:
    """Agent 运行器 - 使用 LangGraph 管理交互式会话"""

    def __init__(self):
        self.state = None
        self.pending_question = None
        self.pending_field = None  # 当前正在询问的字段
        self.langgraph_agent = None
        self.llm_client = None
        self.last_assistant_message = ""
        self._pre_last_assistant = ""

    def _is_waiting_answer(self) -> bool:
        """判断是否为等待用户回复的占位答案"""
        answer = self.state.get("final_answer", "")
        if not answer:
            return False
        return "等待用户" in answer or "等待回复" in answer

    def initialize(self):
        """初始化 Agent"""
        try:
            # 验证环境配置
            from config.settings import settings

            if not settings.LLM_API_KEY:
                print_warning("未配置 LLM_API_KEY! 请检查 .env 文件")
                print_info("提示: 复制 .env.example 为 .env 并填入 API Key")
                return False

            print_info(f"LLM 配置: {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")

            # 注册工具
            from tools.registry import register_all_tools
            register_all_tools()

            # 导入 LangGraph Agent
            from agent.graph import compile_agent
            self.langgraph_agent = compile_agent()
            print_info("LangGraph Agent 已加载")

            # 测试 LLM 连接
            from config.llm_config import get_llm_client
            self.llm_client = get_llm_client()

            print_success("Agent 初始化完成")

            # 打印 LangSmith 状态
            if settings.LANGCHAIN_TRACING_V2:
                print_info(f"LangSmith 追踪已启用: {settings.LANGCHAIN_PROJECT}")

            return True

        except ImportError as e:
            print_warning(f"导入失败: {e}")
            print_info("请运行: pip install -e '.[dev,llm]'")
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            print_warning(f"初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start_session(self, initial_message: str) -> bool:
        """开始新会话"""
        from agent.state import create_initial_state
        from agent.nodes.input_parser import identify_scenario

        # 自动识别场景类型（基于初始消息）
        detected_scenario = identify_scenario(initial_message)

        session_id = f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.state = create_initial_state(
            session_id=session_id,
            scenario_type=detected_scenario,
            initial_message=initial_message,
        )
        self.state["awaiting_user"] = False

        print_info(f"会话 ID: {session_id}")
        print_info(f"识别场景: {detected_scenario}")
        return True

    def _parse_pending_field_value(self, message: str, field: str) -> Optional[str]:
        """
        智能解析 pending_field 对应的值

        当用户回答具体值（如"关车"、"运转"）但未被正则匹配时使用
        """
        text = message.strip().lower()

        if field == "engine_status":
            # 发动机状态关键词
            stopped_keywords = ["关车", "关闭", "关", "停车", "熄火", "停了", "停止", "已关", "已停"]
            running_keywords = ["运转", "运行", "转", "工作", "启动", "在转", "慢车", "启动中"]
            for kw in stopped_keywords:
                if kw in text:
                    return "STOPPED"
            for kw in running_keywords:
                if kw in text:
                    return "RUNNING"

        elif field == "continuous":
            # 持续性关键词
            true_keywords = ["是", "有", "持续", "还在", "不断", "一直", "在漏", "滴漏", "流淌"]
            false_keywords = ["没", "不", "没有", "停止", "止住", "停了", "已停", "没了", "关闭"]
            for kw in true_keywords:
                if kw in text and "不" not in text:
                    return True
            for kw in false_keywords:
                if kw in text:
                    return False

        elif field == "leak_size":
            # 面积关键词
            if any(kw in text for kw in ["大", "很大", "大量", ">5", "5㎡"]):
                return "LARGE"
            elif any(kw in text for kw in ["中", "一般", "1-5"]):
                return "MEDIUM"
            elif any(kw in text for kw in ["小", "少量", "一点", "<1"]):
                return "SMALL"

        elif field == "fluid_type":
            # 油液类型关键词
            if any(kw in text for kw in ["燃油", "航油", "油料", "jet", "fuel", "漏油", "煤油"]):
                return "FUEL"
            elif any(kw in text for kw in ["液压油", "液压", "hydraulic"]):
                return "HYDRAULIC"
            elif any(kw in text for kw in ["滑油", "机油", "润滑油", "oil"]):
                return "OIL"

        elif field == "position":
            # 位置关键词 - 尝试提取纯数字或字母+数字
            import re
            # 匹配 2-3 位数字（机位号）
            match = re.search(r'\b(\d{2,3})\b', text)
            if match:
                return match.group(1)
            # 匹配字母+数字（如 A3, W2）
            match = re.search(r'\b([A-Z]\d+)\b', text.upper())
            if match:
                return match.group(1)
            # 匹配数字+滑行道/跑道
            match = re.search(r'(\d+)\s*(?:滑行道|跑道|twy|rwy)', text)
            if match:
                return match.group(1)

        return None

    def run_step(self) -> Dict[str, Any]:
        """执行一次 LangGraph invoke"""
        if not self.state:
            return {"status": "error", "message": "状态未初始化"}

        # 检查是否完成
        if self.state.get("is_complete") or self.state.get("fsm_state") == "COMPLETED":
            return {
                "status": "completed",
                "report": self.state.get("final_report", {}),
                "answer": self.state.get("final_answer", ""),
            }

        try:
            # 记录当前最新的 assistant 消息，避免重复追问
            pre_last_assistant = self._get_latest_assistant_message()
            self._pre_last_assistant = pre_last_assistant
            if pre_last_assistant:
                self.last_assistant_message = pre_last_assistant
            pre_message_count = len(self.state.get("messages", []))

            # 使用 stream 来显示中间步骤
            # 导入配置
            from agent.graph import get_agent_config
            agent_config = get_agent_config()

            for chunk in self.langgraph_agent.stream(self.state, config=agent_config):
                # chunk 是一个字典，key 是节点名，value 是该节点的输出
                for node_name, node_output in chunk.items():
                    # 更新状态
                    if isinstance(node_output, dict):
                        self.state.update(node_output)

                    # 显示节点执行结果
                    if node_name == "input_parser" and node_output:
                        self._display_node_result(node_name, node_output)
                    elif node_name == "reasoning" and node_output:
                        if node_output.get("current_thought"):
                            print_thought(node_output.get("current_thought", ""))
                        if node_output.get("current_action"):
                            print_action(node_output.get("current_action", ""), node_output.get("current_action_input", {}))

                    elif node_name == "tool_executor" and node_output:
                        if node_output.get("current_observation"):
                            print_observation(node_output.get("current_observation", ""))

                    # 如果需要用户输入，立即返回
                    if node_output.get("awaiting_user"):
                        break

            # 最后一次状态检查（确保拿到最终状态）
            # stream 结束后 self.state 已经是最新的了

            # 检查报告是否已生成但等待用户确认
            if self.state.get("report_generated") and not self.state.get("is_complete"):
                question = self._get_latest_assistant_message()
                if not question:
                    # 如果没有获取到消息，使用默认询问
                    incident = self.state.get("incident", {})
                    flight_no = incident.get("flight_no_display") or incident.get("flight_no") or ""
                    question = f"{flight_no}，处置流程已完成。你还有什么需要补充的吗？" if flight_no else "处置流程已完成。你还有什么需要补充的吗？"
                return {
                    "status": "need_confirmation",
                    "question": question,
                }

            # 已完成直接返回
            if self.state.get("is_complete") or (self.state.get("final_answer") and not self._is_waiting_answer()):
                return {
                    "status": "completed",
                    "report": self.state.get("final_report", {}),
                    "answer": self.state.get("final_answer", ""),
                }

            # 等待用户回复
            if self.state.get("awaiting_user") or self._is_waiting_answer():
                question = self._get_latest_assistant_message()

                # 检查是否出现重复提问（基于消息历史而非简单文本比较）
                duplicate_count = self.state.get("_duplicate_question_count", 0)
                last_asked_question = self.state.get("_last_asked_question", "")

                if question and question == last_asked_question:
                    # 如果是相同问题，增加计数器
                    duplicate_count += 1
                    self.state["_duplicate_question_count"] = duplicate_count

                    # 如果重复次数过多（超过3次），重置状态并继续推理
                    if duplicate_count >= 3:
                        print_warning("检测到重复提问超过3次，重置状态并重新评估...")
                        self.state["_duplicate_question_count"] = 0
                        self.state["_last_asked_question"] = ""
                        self.state["pending_question"] = None
                        self.state["pending_field"] = None
                        # 清除awaiting标志，让系统重新进入推理
                        self.state["awaiting_user"] = False
                        # 继续循环，让系统重新评估状态
                        return {"status": "continue"}
                else:
                    # 新问题，重置计数器
                    self.state["_duplicate_question_count"] = 1
                    self.state["_last_asked_question"] = question or ""

                if question:
                    self.last_assistant_message = question
                return {
                    "status": "need_input",
                    "question": question or "请提供更多信息",
                    "field": "",
                }

            # 检查是否出现新的 assistant 提问
            messages = self.state.get("messages", [])
            if len(messages) > pre_message_count:
                question = self._get_latest_assistant_message()
                if question and question != pre_last_assistant:
                    self.last_assistant_message = question
                    return {
                        "status": "need_input",
                        "question": question,
                        "field": "",
                    }

            # 检查错误
            if self.state.get("error"):
                error_msg = self.state["error"]
                self.state["error"] = ""
                return {"status": "error", "message": error_msg}

            return {"status": "continue"}

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def run_until_pause(self) -> Dict[str, Any]:
        """运行 Agent 直到需要用户输入或完成"""
        max_steps = 5
        for _ in range(max_steps):
            result = self.run_step()
            status = result.get("status")
            if status != "continue":
                return result
        return {"status": "error", "message": "超过最大步骤数"}

    def add_user_message(self, message: str):
        """添加用户消息"""
        if not self.state:
            return

        # 添加消息到历史
        messages = self.state.get("messages", [])
        messages.append({"role": "user", "content": message})
        self.state["messages"] = messages
        self.pending_question = None
        self.pending_field = None
        self.state["is_complete"] = False
        self.state["next_node"] = "input_parser"
        self.state["awaiting_user"] = False

        # 重置重复提问相关状态
        self.state["_duplicate_question_count"] = 0
        self.state["_last_asked_question"] = ""

    def _get_latest_assistant_message(self) -> str:
        """获取最近一条 assistant 消息"""
        messages = self.state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""

    def _print_flight_plan_brief(self, table: str, incident: Dict[str, Any]):
        """简洁格式打印航班计划"""
        # 解析表格提取关键信息
        lines = table.strip().split("\n")
        if len(lines) < 3:
            print_dim(f"  {table}")
            return

        # 跳过表头和分隔线，取数据行
        data_lines = [l for l in lines[2:] if l.strip() and not l.startswith("-")]
        if not data_lines:
            return

        # 解析第一行数据
        row = data_lines[0]
        parts = [p.strip() for p in row.split("|")]
        if len(parts) >= 4:
            callsign = parts[0] if parts[0] else "N/A"
            inorout = "出发" if parts[1] == "D" else "到达" if parts[1] == "A" else parts[1]
            stand = parts[2] if parts[2] else "N/A"
            runway = parts[3] if parts[3] else "N/A"

            # 提取时间（优先显示计划时间）
            time_str = ""
            if len(parts) >= 6:
                etot = parts[5].strip() if len(parts) > 5 else ""  # 计划起飞
                eldt = parts[4].strip() if len(parts) > 4 else ""  # 计划落地
                if inorout == "出发" and etot:
                    time_str = f"计划起飞 {etot.split(' ')[1] if ' ' in etot else etot}"
                elif inorout == "到达" and eldt:
                    time_str = f"计划落地 {eldt.split(' ')[1] if ' ' in eldt else eldt}"

            print_dim(f"  呼号: {callsign} | 类型: {inorout} | 机位: {stand} | 跑道: {runway}")
            if time_str:
                print_dim(f"  {time_str}")

    def _should_pause_for_input(self) -> bool:
        """检查是否应该暂停等待用户输入"""
        return False

    def _display_node_start(self, node_name: str):
        """显示节点开始执行"""
        node_names = {
            "input_parser": "输入解析",
            "reasoning": "ReAct 推理",
            "tool_executor": "工具执行",
            "fsm_validator": "FSM 验证",
            "output_generator": "报告生成",
        }
        name = node_names.get(node_name, node_name)
        print(f"\n[{name}]")

    def _display_node_result(self, node_name: str, output: Dict[str, Any]):
        """显示节点执行结果"""

        if node_name == "input_parser":
            incident = output.get("incident", {})
            extracted = []
            field_names = {
                "fluid_type": "油液类型",
                "position": "位置",
                "engine_status": "发动机",
                "continuous": "持续泄漏",
                "leak_size": "面积",
                "flight_no": "航班号",
            }
            # 只显示本次提取的字段（如果有reasoning_steps记录的话）
            reasoning_steps = output.get("reasoning_steps", [])
            if reasoning_steps and len(reasoning_steps) > 0:
                last_step = reasoning_steps[-1]
                if "提取实体:" in last_step.get("observation", ""):
                    # 从observation中提取实体信息并显示
                    obs = last_step.get("observation", "")
                    if "提取实体:" in obs:
                        entities_str = obs.split("提取实体:")[1].split("\n")[0].strip()
                        print_info(f"本次提取: {entities_str}")

            # 显示当前incident的完整状态
            for k, v in incident.items():
                if v is not None and k in field_names:
                    name = field_names.get(k, k)
                    if k == "position" and incident.get("position_display"):
                        extracted.append(f"{name}={incident['position_display']}")
                    else:
                        extracted.append(f"{name}={v}")
            if extracted:
                print_info(f"已收集信息: {', '.join(extracted)}")

            # 显示气象信息
            weather = output.get("weather", {})
            if weather:
                weather_parts = []
                if weather.get("location"):
                    weather_parts.append(f"观测点: {weather['location']}")
                if weather.get("wind_speed") is not None:
                    wind_dir = f"{weather.get('wind_direction', 0):.0f}°" if weather.get('wind_direction') else "未知"
                    weather_parts.append(f"风: {wind_dir} {weather['wind_speed']:.1f}m/s")
                if weather.get("temperature") is not None:
                    weather_parts.append(f"温度: {weather['temperature']:.1f}°C")
                if weather_parts:
                    print_info(f"气象条件: {', '.join(weather_parts)}")

            # 仅在首次获取时显示航班计划（避免重复）
            if not self.state.get("_flight_plan_displayed"):
                flight_plan_table = output.get("flight_plan_table") or self.state.get("flight_plan_table")
                if flight_plan_table:
                    self.state["_flight_plan_displayed"] = True
                    print_info("航班计划:")
                    self._print_flight_plan_brief(flight_plan_table, incident)
                elif not self.state.get("flight_plan_checked"):
                    # Fallback: 如果没有从 auto_enrichment 获取到，手动查询一次
                    flight_no = incident.get("flight_no") or incident.get("flight_no_display")
                    if flight_no:
                        try:
                            from tools.information.flight_plan_lookup import FlightPlanLookupTool
                            tool = FlightPlanLookupTool()
                            result = tool.execute(incident, {"flight_no": flight_no})
                            table = result.get("flight_plan_table")
                            if table:
                                self.state["flight_plan_table"] = table
                                self.state["_flight_plan_displayed"] = True
                                print_info("航班计划:")
                                self._print_flight_plan_brief(table, incident)
                        except Exception:
                            pass
                        finally:
                            self.state["flight_plan_checked"] = True

            # 显示位置影响分析结果
            position_impact = output.get("position_impact_analysis", {})
            if position_impact:
                print_info(f"位置特定影响分析:")
                direct = position_impact.get("direct_impact", {})
                if direct.get("affected_facility"):
                    print_info(f"  事发设施: {direct['affected_facility']}")
                if direct.get("closure_time_minutes"):
                    print_info(f"  预计封闭: {direct['closure_time_minutes']} 分钟")
                if direct.get("severity_score"):
                    print_info(f"  严重程度: {direct['severity_score']:.1f}/5.0")

                adjacent = position_impact.get("adjacent_impact", {})
                if adjacent.get("total_adjacent", 0) > 0:
                    count_by_type = adjacent.get("count_by_type", {})
                    if count_by_type.get("机位", 0) > 0:
                        print_info(f"  相邻机位影响: {count_by_type['机位']} 个")
                    if count_by_type.get("滑行道", 0) > 0:
                        print_info(f"  相邻滑行道影响: {count_by_type['滑行道']} 条")
                    if count_by_type.get("跑道", 0) > 0:
                        print_info(f"  相邻跑道影响: {count_by_type['跑道']} 条")

                efficiency = position_impact.get("efficiency_impact", {})
                if efficiency.get("description"):
                    print_info(f"  运行效率: {efficiency['description']}")
                if efficiency.get("delay_per_flight"):
                    print_info(f"  预计延误: {efficiency['delay_per_flight']} 分钟/架次")
                if efficiency.get("capacity_reduction_percent"):
                    print_info(f"  容量降低: {efficiency['capacity_reduction_percent']}%")

        elif node_name == "reasoning":
            thought = output.get("current_thought", "")
            if thought:
                print_thought(thought)

            action = output.get("current_action", "")
            if action:
                action_input = output.get("current_action_input", {})
                print_action(action, action_input)

            if output.get("final_answer"):
                print_success("推理完成，准备生成报告")

        elif node_name == "tool_executor":
            observation = output.get("current_observation", "")
            if observation:
                print_observation(observation)

            if output.get("risk_assessment"):
                risk = output["risk_assessment"]
                level = risk.get("level", "")
                score = risk.get("score", 0)
                print_info(f"风险: {level} ({score}/100) - {risk.get('rationale', '')}")

            if output.get("spatial_analysis"):
                spatial = output["spatial_analysis"]
                print_info(f"影响范围分析:")
                if spatial.get("anchor_node"):
                    print_info(f"  起始节点: {spatial['anchor_node']} ({spatial.get('anchor_node_type', '')})")
                if spatial.get("isolated_nodes"):
                    print_info(f"  隔离区域: {len(spatial['isolated_nodes'])} 个节点")
                if spatial.get("affected_stands"):
                    print_info(f"  受影响机位: {', '.join(spatial['affected_stands'][:5])}")
                if spatial.get("affected_taxiways"):
                    print_info(f"  受影响滑行道: {', '.join(spatial['affected_taxiways'][:5])}")
                if spatial.get("affected_runways"):
                    print_info(f"  受影响跑道: {', '.join(spatial['affected_runways'])}")

            if output.get("flight_impact_prediction"):
                flight_impact = output["flight_impact_prediction"]
                stats = flight_impact.get("statistics", {})
                if stats:
                    total = stats.get("total_affected_flights", 0)
                    avg_delay = stats.get("average_delay_minutes", 0)
                    print_info(f"航班影响预测: {total} 架次, 平均延误 {avg_delay:.1f} 分钟")

        elif node_name == "fsm_validator":
            fsm_state = output.get("fsm_state", "")
            errors = output.get("fsm_validation_errors", [])

            if fsm_state:
                print_fsm(fsm_state)

            if errors:
                for error in errors:
                    print_warning(f"验证问题: {error}")

        elif node_name == "output_generator":
            print_success("报告生成完成")

    def _check_need_input(self, output: Dict[str, Any]) -> bool:
        """检查是否需要用户输入"""
        action = output.get("current_action", "")

        # 支持 ask_for_detail 和 smart_ask 两种询问工具
        if action in ["ask_for_detail", "smart_ask"]:
            if action == "smart_ask":
                observation = output.get("current_observation", "")
                # 未生成问题时不应继续追问
                if "所有必填字段已收集完成" in observation:
                    return False

            action_input = output.get("current_action_input", {})
            self.pending_field = action_input.get("field", "")
            self.pending_question = None  # 初始化

            # 优先从state的messages中获取工具执行后的问题（已添加机号前缀）
            messages = self.state.get("messages", [])
            if messages:
                # 获取最后一条assistant消息
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        self.pending_question = msg.get("content", "")
                        break

            # 如果没有找到，使用原始输入作为fallback
            if not self.pending_question:
                self.pending_question = action_input.get("question", "请提供更多信息")

            return True
        return False


# ============================================================
# 主程序
# ============================================================

def print_final_report(report: Dict[str, Any], answer: str = ""):
    """打印最终报告"""
    print_header("处置报告")

    if answer:
        print(answer)
        return

    if not report:
        print_warning("报告为空")
        return

    if report.get("title"):
        print(f"{report['title']}\n")

    if report.get("event_summary"):
        print(f"【事件摘要】")
        print(report["event_summary"])
        print()

    if report.get("risk_level"):
        print(f"【风险等级】{report['risk_level']}\n")

    if report.get("handling_process"):
        print(f"【处置过程】")
        for step in report["handling_process"]:
            print(f"  - {step}")
        print()

    if report.get("checklist_items"):
        print(f"【检查单】")
        for category in report["checklist_items"]:
            print(f"  {category.get('category', '')}:")
            for item in category.get("items", []):
                status = "[v]" if item.get("status") == "completed" else "[x]"
                print(f"    {status} {item.get('item', '')}")
        print()

    if report.get("coordination_units"):
        print(f"【协调单位】")
        for unit in report["coordination_units"]:
            if isinstance(unit, dict):
                name = unit.get("name", "")
                notified = "已通知" if unit.get("notified") else "未通知"
                print(f"  - {name} ({notified})")
            else:
                print(f"  - {unit}")
        print()

    if report.get("recommendations"):
        print(f"【处置建议】")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"  {i}. {rec}")
        print()

    if report.get("generated_at"):
        print_dim(f"报告生成时间: {report['generated_at']}")


def save_report(state: Dict[str, Any], report: Dict[str, Any], answer: str = "") -> str:
    """保存报告到文件（Markdown格式）"""
    import json

    # 获取场景类型，用于按场景分类存储
    scenario_type = state.get("scenario_type", "oil_spill")

    # 根据场景类型创建对应的文件夹路径
    scenario_folder_map = {
        "oil_spill": "oil_spill",
        "bird_strike": "bird_strike",
        "fod": "fod"
    }

    # 获取场景文件夹名称，默认为 "other"
    scenario_folder = scenario_folder_map.get(scenario_type, "other")

    # 创建按场景分类的报告目录
    reports_dir = os.path.join(PROJECT_ROOT, "outputs", "reports", scenario_folder)
    os.makedirs(reports_dir, exist_ok=True)

    session_id = state.get("session_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 获取航班号用于文件名
    incident = state.get("incident", {})
    flight_no = incident.get("flight_no", "")

    # 生成文件名
    if flight_no:
        md_filename = os.path.join(reports_dir, f"检查单_{flight_no}_{timestamp}.md")
    else:
        md_filename = os.path.join(reports_dir, f"检查单_{session_id}_{timestamp}.md")

    # 保存 Markdown 报告
    with open(md_filename, "w", encoding="utf-8") as f:
        if answer:
            # LLM 生成的 Markdown 报告
            f.write(answer)
        else:
            # 回退格式
            f.write("# 机坪特情处置检查单\n\n")
            f.write(f"**会话ID**: {session_id}\n")
            f.write(f"**生成时间**: {datetime.now().isoformat()}\n\n")

            if report.get("event_summary"):
                f.write("## 事件摘要\n")
                f.write(report["event_summary"] + "\n\n")

            if report.get("risk_level"):
                f.write(f"## 风险等级: {report['risk_level']}\n\n")

            if report.get("handling_process"):
                f.write("## 处置过程\n")
                for step in report["handling_process"]:
                    f.write(f"- {step}\n")
                f.write("\n")

            if report.get("recommendations"):
                f.write("## 处置建议\n")
                for i, rec in enumerate(report["recommendations"], 1):
                    f.write(f"1. {rec}\n")
                f.write("\n")

    # 保存 JSON 格式（供程序使用）
    json_filename = os.path.join(reports_dir, f"data_{timestamp}.json")
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump({
            "session_id": session_id,
            "generated_at": datetime.now().isoformat(),
            "incident": incident,
            "risk_assessment": state.get("risk_assessment", {}),
            "spatial_analysis": state.get("spatial_analysis", {}),
            "checklist": state.get("checklist", {}),
            "fsm_state": state.get("fsm_state", ""),
            "actions_taken": state.get("actions_taken", []),
            "notifications_sent": state.get("notifications_sent", []),
        }, f, ensure_ascii=False, indent=2)

    return md_filename


def main():
    """主函数"""
    print_header("机场机坪特情应急响应 Agent")
    print_info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print_info("使用 ReAct + FSM 融合架构")
    print_info("命令: 'status' 查看状态, 'exit' 退出")
    print()

    # 初始化 Agent
    runner = AgentRunner()
    if not runner.initialize():
        return 1

    print()
    print_agent("天府机坪，请讲。")

    first_contact_done = False

    # 获取初始输入
    user_input = get_user_input()
    if not user_input or user_input.lower() in ["exit", "quit", "q"]:
        print_info("退出系统")
        return 0
    user_input = apply_readout_for_processing(user_input, is_first_contact=True)
    first_contact_done = True

    # 开始会话
    runner.start_session(user_input)

    # 主循环
    while True:
        result = runner.run_until_pause()
        status = result.get("status")

        if status == "completed":
            print_state_summary(runner.state)
            print_final_report(
                result.get("report", {}),
                result.get("answer", ""),
            )

            report_file = save_report(
                runner.state,
                result.get("report", {}),
                result.get("answer", ""),
            )
            print()
            print_success(f"报告已保存: {report_file}")
            print_success("处置流程完成")
            break

        elif status == "need_confirmation":
            # 报告已生成，询问用户是否需要补充
            question = result.get("question", "处置流程已完成。你还有什么需要补充的吗？")
            print()
            print_agent(format_control_reply(question, runner.state, is_first_contact=False))
            print_info("输入 'y' 或 'yes' 确认结束，或输入补充信息继续处理")

            user_input = get_user_input()

            if not user_input:
                continue
            user_input = apply_readout_for_processing(user_input, is_first_contact=False)

            cmd = user_input.lower().strip()

            # 检查是否是确认结束（包含各种表达方式）
            is_confirm_end = False

            # 简单确认词
            if cmd in ["y", "yes", "是", "确认", "没有", "无", "结束", "ok", "好的", "可以", "完毕"]:
                is_confirm_end = True
            # 否定+补充的组合（表示没有要补充的）
            elif any(neg in cmd for neg in ["没", "无", "不", "没有"]) and \
                 any(word in cmd for word in ["补充", "其他", "问题", "情况", "要说", "要补", "要报"]):
                is_confirm_end = True
            elif any(phrase in cmd for phrase in ["无信息补充", "无需补充", "没信息补充", "没有补充", "无补充"]):
                is_confirm_end = True
            # 纯数字或字母（可能是误输入，但不应该被当作补充信息）
            elif len(cmd) <= 2 and not any(c.isalpha() and ord(c) > 127 for c in cmd):
                # 如果输入很短且不包含中文，可能是误输入，询问用户
                print_warning("输入过短，如需结束请输入 'y' 或 'yes'")
                continue

            if is_confirm_end:
                # 用户确认结束，使用已生成的终版报告；如缺失则补生成
                if (
                    not runner.state.get("final_report")
                    or not runner.state.get("final_answer")
                    or runner._is_waiting_answer()
                ):
                    from agent.nodes.output_generator import output_generator_node
                    updates = output_generator_node(runner.state)
                    runner.state.update(updates)
                from agent.state import FSMState
                runner.state["fsm_state"] = FSMState.COMPLETED.value
                runner.state["report_generated"] = False
                runner.state["awaiting_user"] = False
                runner.state["is_complete"] = True
                # 继续循环，会在下次迭代时进入 completed 分支
                continue
            else:
                # 用户提供了补充信息，继续处理
                runner.state["report_generated"] = False  # 重置标志，允许再次生成报告
                runner.add_user_message(user_input)

        elif status == "need_input":
            question = result.get("question", "请提供更多信息")
            print()
            print_agent(format_control_reply(question, runner.state, is_first_contact=not first_contact_done))

            user_input = get_user_input()

            if not user_input:
                # 空输入处理：检查是否需要澄清问题
                if "是否" in question and question.count("是否") >= 2:
                    # 如果问题包含多个"是否"，可能用户困惑，尝试澄清
                    print_info("检测到问题可能表述不清，自动澄清...")
                    # 强制清除状态，让系统重新推理
                    runner.state["awaiting_user"] = False
                    runner.state["_duplicate_question_count"] = 0
                    runner.state["_last_asked_question"] = ""
                    runner.state["next_node"] = "reasoning"
                    continue
                continue
            user_input = apply_readout_for_processing(user_input, is_first_contact=False)

            cmd = user_input.lower()
            if cmd in ["exit", "quit", "q"]:
                print_info("用户退出")
                break
            elif cmd == "status":
                print_state_summary(runner.state)
                continue

            runner.add_user_message(user_input)

        elif status == "error":
            print_warning(f"执行错误: {result.get('message', '未知错误')}")

            user_input = get_user_input("是否继续? (y/n)")
            if user_input.lower() not in ["y", "yes", "是"]:
                break

        else:
            print_warning(f"未知状态: {status}")
            break

    print()
    print_info("感谢使用机坪应急响应系统")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n")
        print_info("用户中断")
        sys.exit(0)
    except Exception as e:
        print_warning(f"程序错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
