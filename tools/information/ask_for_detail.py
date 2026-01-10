"""
信息追问工具 - 机坪管制员向机长询问
"""
from typing import Dict, Any
from tools.base import BaseTool


class AskForDetailTool(BaseTool):
    """机坪管制员询问机长信息（自动添加机号称呼）"""

    name = "ask_for_detail"
    description = """向机长询问缺失的信息。工具会自动在问题前添加机号称呼。

输入参数:
- question: 要询问的问题（直接写问题内容，不要加机号或"机长"）
- field: 对应的字段名（如 fluid_type, leak_size 等）

使用场景:
- Checklist 中有未收集的字段时
- 需要确认关键信息时

重要：
- 如果已知机号，工具会自动添加"[机号]，"前缀
- 问题中不要使用"机长"称呼，使用机号
- 如果询问机号本身，则不添加前缀

示例输入：
- question="报告你机号", field="flight_no" → 输出："报告你机号"
- question="发动机状态？", field="engine_status" → 输出："南航3456，发动机状态？"
- question="还在漏吗？", field="continuous" → 输出："南航3456，还在漏吗？"
"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        question = inputs.get("question", "报告详情")
        field = inputs.get("field", "")

        # 获取航班号，如果已知则在问题前加上机号称呼
        incident = state.get("incident", {})
        # 使用原始显示格式进行呼叫
        flight_no = incident.get("flight_no_display") or incident.get("flight_no")

        # 强制添加机号前缀（如果已知机号且不是在询问机号本身）
        if flight_no and field != "flight_no":
            # 检查 question 是否已经包含机号（避免重复添加）
            # 直接使用原始格式，不再转换
            if not question.startswith(flight_no):
                question = f"{flight_no}，{question}"

        # 生成询问消息
        observation = f"已询问: {question}"

        # 添加到消息列表
        new_message = {
            "role": "assistant",
            "content": question,
        }

        return {
            "observation": observation,
            "messages": [new_message],
        }
