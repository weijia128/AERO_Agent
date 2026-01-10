"""
智能问题生成工具 - 根据缺失字段智能合并问题
"""
from typing import Dict, Any, List, Tuple
from tools.base import BaseTool
from config.airline_codes import format_callsign_display


# 字段中文名称
FIELD_NAMES = {
    "flight_no": "航班号",
    "position": "位置（停机位/滑行道/跑道）",
    "fluid_type": "油液类型（燃油/液压油/滑油）",
    "engine_status": "发动机状态（运转/关车）",
    "continuous": "是否持续滴漏",
    "leak_size": "泄漏面积",
}

# 字段追问提示
ASK_PROMPTS = {
    "flight_no": "报告你机号",
    "position": "具体位置（停机位号/滑行道/跑道）？",
    "fluid_type": "泄漏的油液类型？燃油、液压油还是滑油？",
    "engine_status": "发动机当前状态？运转中还是已关闭？",
    "continuous": "是否还在持续滴漏？",
    "leak_size": "目测泄漏面积大概多大？",
}


def get_missing_fields(incident: Dict[str, Any], checklist: Dict[str, bool]) -> List[str]:
    """获取未收集的必填字段（仅P1字段）"""
    required_fields = ["fluid_type", "position", "engine_status", "continuous"]
    missing = []
    for field in required_fields:
        # 修复：只检查 incident 中是否有值，不依赖 checklist 标记
        # 原因：checklist 标记可能更新不及时，导致已提取的字段仍被认为缺失
        value = incident.get(field)
        if value is None:
            missing.append(field)
    return missing


def group_missing_fields(missing: List[str]) -> List[List[str]]:
    """将缺失字段分组，每组最多2个相关字段"""
    groups = []
    remaining = missing.copy()

    # 定义相关性分组优先级（按场景分组）
    priority_groups = [
        # 核心信息组：位置+油液+发动机
        ["position", "fluid_type", "engine_status"],
        # 持续性单独或与发动机配对
        ["engine_status", "continuous"],
        # 位置+油液配对
        ["position", "fluid_type"],
    ]

    while remaining:
        field = remaining[0]
        grouped = False

        # 尝试按优先级分组
        for priority_group in priority_groups:
            if field in priority_group:
                # 找出同组中所有未收集的字段
                group_fields = [f for f in priority_group if f in remaining]
                # 每组最多2个字段
                if len(group_fields) >= 2:
                    groups.append(group_fields[:2])
                    for f in group_fields[:2]:
                        remaining.remove(f)
                else:
                    groups.append([f for f in group_fields])
                    for f in group_fields:
                        remaining.remove(f)
                grouped = True
                break

        if not grouped:
            # 单独添加
            groups.append([field])
            remaining.remove(field)

    return groups


def build_combined_question(fields: List[str], flight_no: str = None) -> str:
    """根据字段列表构建合并的问题"""
    if len(fields) == 1:
        # 单个字段
        question = ASK_PROMPTS.get(fields[0], f"请提供{FIELD_NAMES.get(fields[0], fields[0])}")
    elif len(fields) == 2:
        # 两个字段合并
        prompts = [ASK_PROMPTS.get(f, FIELD_NAMES.get(f, f)) for f in fields]
        # 组合问题，用问号分隔
        if prompts[0].endswith("？") or prompts[0].endswith("?"):
            question = prompts[0] + " " + prompts[1]
        else:
            question = "？".join(prompts) + "？"
    else:
        # 多个字段，限制数量
        prompts = [ASK_PROMPTS.get(f, FIELD_NAMES.get(f, f)) for f in fields[:2]]
        question = "？".join(prompts) + "？"

    # 添加航班号前缀（统一格式化显示）
    if flight_no and "报告你机号" not in question:
        callsign = format_callsign_display(flight_no)
        if callsign and not question.startswith(callsign):
            question = f"{callsign}，{question}"

    return question


class SmartAskTool(BaseTool):
    """智能问题生成工具 - 根据缺失字段自动合并问题"""

    name = "smart_ask"
    description = """智能生成合并的问题询问。

功能：
- 根据当前已收集的信息，判断还缺少哪些必填字段
- 将相关字段合并为一个问题（最多2个字段/问题）
- 自动添加航班号前缀

输入参数:
- 无需参数（从状态自动获取缺失字段）

返回:
- 生成的问题
- 缺失字段列表
- 字段分组信息
"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        incident = state.get("incident", {})
        checklist = state.get("checklist", {})

        # 获取缺失字段
        missing = get_missing_fields(incident, checklist)

        if not missing:
            return {
                "observation": "所有P1必填字段已收集完成，可以立即进行风险评估",
                "missing_fields": [],
                "question": None,
                "ready_for_assessment": True,
                "messages": [],  # 无需发送消息
            }

        # 分组
        groups = group_missing_fields(missing)

        # 生成第一个问题（取第一个分组）
        first_group = groups[0] if groups else []
        # 使用原始显示格式进行呼叫
        flight_no = incident.get("flight_no_display") or incident.get("flight_no")
        question = build_combined_question(first_group, flight_no)

        # 生成要发送的消息
        new_message = {
            "role": "assistant",
            "content": question,
        }

        return {
            "observation": f"已询问: {question}",
            "missing_fields": missing,
            "field_groups": groups,
            "question": question,
            "current_group": first_group,
            "ready_for_assessment": False,
            "messages": [new_message],  # 关键：返回消息列表
        }


def get_next_questions(state: Dict[str, Any]) -> Tuple[str, List[str]]:
    """获取下一组问题和缺失字段列表"""
    incident = state.get("incident", {})
    checklist = state.get("checklist", {})

    missing = get_missing_fields(incident, checklist)
    if not missing:
        return None, []

    groups = group_missing_fields(missing)
    first_group = groups[0] if groups else []
    question = build_combined_question(first_group, incident.get("flight_no"))

    return question, missing
