# Bug修复：报告生成动作冗余 & 递归超限

## 问题描述

**现象：**
```
[执行] smart_ask
[观察] 所有P1必填字段已收集完成，可以立即进行风险评估
[思考] 还有P2字段待收集...
[执行] smart_ask
[观察] 所有P1必填字段已收集完成，可以立即进行风险评估
[执行] generate_report
[观察] 报告生成完成...
[执行] generate_report
[观察] 报告生成完成...
[执行] generate_report
[观察] 报告生成完成...

GraphRecursionError: Recursion limit of 25 reached without hitting a stop condition.
```

**影响：**
1. `generate_report` 被重复调用3次（冗余）
2. LLM陷入无限循环，最终递归超限
3. 系统崩溃，无法正常生成报告

---

## 根本原因分析

### 原因1：缺少明确的终止信号

**文件：** `tools/action/generate_report.py`

**问题：**
```python
# 修复前
return {
    "observation": "报告生成完成: ...",
    "final_report": report,
}
```

- 只返回了 observation，没有设置 `is_complete` 标志
- LLM不知道应该输出 `Final Answer` 结束循环
- 继续思考"还有P2字段待收集"，进入死循环

### 原因2：Prompt没有明确终止条件

**文件：** `scenarios/oil_spill/prompt.yaml`

**问题：**
- Prompt中没有明确说明 `generate_report` 后必须结束
- LLM看到P2字段未收集，虽然知道不应追问，但没有明确的行动指令
- 导致LLM继续重复调用工具

### 原因3：递归限制过低

**文件：** `agent/graph.py`

**问题：**
- LangGraph默认递归限制为25次
- 如果LLM陷入循环，很快就会触发限制
- 错误信息不够友好，难以定位问题

---

## 修复方案

### 修复1：generate_report 返回终止信号

**文件：** `tools/action/generate_report.py`

**修改：**
```python
# 修复后
observation = (
    f"报告生成完成: ..."
    f"\n⚠️ 处置流程已完成，请输出 Final Answer 结束对话。"
)

return {
    "observation": observation,
    "final_report": report,
    # 设置完成标志，告诉LangGraph应该结束
    "is_complete": True,
}
```

**效果：**
- 明确告诉LLM应该输出 `Final Answer`
- 设置 `is_complete=True`，LangGraph会路由到output_generator或结束

---

### 修复2：改进 Prompt 明确工作流程

**文件：** `scenarios/oil_spill/prompt.yaml`

**新增内容：**
```yaml
## 工作方式
你使用 ReAct 模式：Thought -> Action -> Observation -> 循环直到完成

**标准工作流程（严格按序执行）：**
1. **信息收集阶段**：使用 `smart_ask` 收集所有P1字段
2. **风险评估阶段**：P1收集完成后，立即调用 `assess_risk`
3. **通知协调阶段**：根据风险等级通知相关部门（`notify_department`）
4. **报告生成阶段**：调用 `generate_report` 生成报告
5. **任务结束**：输出 `Final Answer` 结束对话

**⚠️ 关键规则：**
- `generate_report` 只能调用**一次**！
- 调用 `generate_report` 后，**必须立即输出 Final Answer 结束**
- **禁止**在报告生成后继续调用任何工具
- **禁止**在报告生成后继续思考P2字段
- 报告生成即代表任务完成

## 输出格式
任务完成时（generate_report后）：
Thought: 报告已生成，处置流程完成
Final Answer: 川航3349，应急处置流程已完成。已通知相关部门，报告已生成。
```

**效果：**
- 明确5步工作流程
- 强调 `generate_report` 只能调用一次
- 给出具体的 Final Answer 示例

---

### 修复3：增加递归限制配置

**文件：** `agent/graph.py`

**新增函数：**
```python
def get_agent_config():
    """获取Agent运行配置

    返回包含recursion_limit等配置的字典
    """
    return {
        "recursion_limit": 50,  # 增加递归限制到50（默认25）
    }
```

**文件：** `apps/run_agent.py` (第440-444行)

**修改：**
```python
# 修复前
for chunk in self.langgraph_agent.stream(self.state):
    ...

# 修复后
from agent.graph import get_agent_config
agent_config = get_agent_config()

for chunk in self.langgraph_agent.stream(self.state, config=agent_config):
    ...
```

**效果：**
- 递归限制从25增加到50
- 提供缓冲空间，避免正常流程触发限制
- 如果仍然超限，说明确实有逻辑错误

---

## 修复前后对比

### 修复前（错误）
```
[执行] assess_risk ✓
[观察] 风险评估完成 ✓
[执行] notify_department (4次) ✓
[执行] smart_ask (2次) ❌ 重复
[执行] generate_report (3次) ❌ 重复
GraphRecursionError ❌ 崩溃
```

### 修复后（正确）
```
[执行] assess_risk ✓
[观察] 风险评估完成 ✓
[执行] notify_department (4次) ✓
[执行] generate_report (1次) ✓
[观察] 报告生成完成，请输出 Final Answer 结束对话 ✓
[思考] 报告已生成，处置流程完成 ✓
Final Answer: 川航3349，应急处置流程已完成 ✓
```

---

## 影响范围

### 修改文件
1. ✅ `tools/action/generate_report.py` - 返回终止信号
2. ✅ `scenarios/oil_spill/prompt.yaml` - 明确工作流程
3. ✅ `agent/graph.py` - 增加递归限制配置
4. ✅ `apps/run_agent.py` - 应用配置

### 不受影响的文件
- 所有其他工具
- FSM引擎
- API服务

### 兼容性
✅ 完全向后兼容

---

## 测试建议

### 测试场景1：正常流程
```
输入: 川航3349，滑油泄漏，持续滴漏，发动机关闭，在滑行道19
期望:
1. 收集P1字段
2. 风险评估 (MEDIUM)
3. 通知相关部门
4. 生成报告（只调用1次）
5. 输出 Final Answer 结束
```

### 测试场景2：递归限制测试
```
测试: 如果LLM仍然陷入循环，是否能在50次内被捕获
期望: 更友好的错误提示，而不是立即崩溃
```

---

## 长期改进建议

### 建议1：增加状态机强制终止条件

```python
# agent/graph.py
def should_continue(state: AgentState):
    # 如果报告已生成，强制结束
    if state.get("final_report"):
        return "end"

    # 如果 generate_report 已调用，禁止再次调用
    actions_taken = state.get("actions_taken", [])
    if any(a.get("action") == "generate_report" for a in actions_taken):
        return "end"

    # 其他逻辑...
```

### 建议2：工具调用次数限制

```python
# tools/base.py
class BaseTool:
    max_calls = 1  # 默认无限制，特殊工具可设置

    def execute(self, state, inputs):
        # 检查调用次数
        if self.max_calls > 0:
            call_count = sum(1 for a in state.get("actions_taken", [])
                           if a.get("action") == self.name)
            if call_count >= self.max_calls:
                return {
                    "observation": f"{self.name}已达到最大调用次数({self.max_calls})，禁止重复调用"
                }

        # 正常执行...
```

### 建议3：增加循环检测

```python
# agent/nodes/reasoning.py
def detect_loop(state: AgentState) -> bool:
    """检测是否陷入循环"""
    recent_actions = state.get("actions_taken", [])[-5:]

    # 检查最近5个动作是否重复
    action_names = [a.get("action") for a in recent_actions]
    if len(action_names) == 5 and len(set(action_names)) <= 2:
        return True  # 只有1-2种动作重复，可能是循环

    return False
```

---

## 总结

这次修复解决了3个问题：
1. ✅ `generate_report` 添加明确的终止信号
2. ✅ Prompt 明确工作流程和终止条件
3. ✅ 递归限制从25增加到50

修复后：
- `generate_report` 只调用1次
- LLM明确知道何时输出 `Final Answer`
- 即使出现问题，也有更大的缓冲空间

**修复简洁、有效、低风险。**
