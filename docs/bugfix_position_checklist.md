# Bug修复：位置重复提问 & P1/Checklist不一致

## 问题复现

### 问题1：重复进行位置提问

**用户输入：**
```
机长: 跑道2 发动机关闭
机长: 滑行道19
```

**系统行为：**
```
机坪管制: 川航3349，具体位置（停机位号/滑行道/跑道）？  # 第1次
机长: 跑道2 发动机关闭
机坪管制: 川航3349，具体位置（停机位号/滑行道/跑道）？  # 第2次
机长: 滑行道19
机坪管制: 川航3349，具体位置（停机位号/滑行道/跑道）？  # 第3次（错误！）
```

### 问题2：P1和Checklist必须收集的不一致

**期望行为：**
- P1字段（必填）：fluid_type, continuous, engine_status, position（4个）
- P2字段（可选）：leak_size, aircraft_reg, flight_no, reported_by, discovery_method（5个）

**实际行为：**
```
[思考] 当前已收集了所有P1必填字段，但Checklist中还有3个次要字段需要收集：
       aircraft_reg（航空器注册号）、reported_by（报告人）和discovery_method（发现方式）。
```

系统把P2字段也当作必须收集的字段了。

---

## 问题分析

### 问题1：位置实体提取失败

**代码位置：** `agent/nodes/input_parser.py`

**问题原因：**

1. **正则匹配后的值重组问题**

当用户输入"跑道2"或"滑行道19"时，正则表达式：
```python
r"(跑道|RWY)[_\s]?(\d{1,2}[LRC]?)"  # 匹配 "跑道2"
r"(滑行道|TWY)[_\s]?([A-Z]?\d+)"   # 匹配 "滑行道19"
```

会捕获两个组：
- group(1) = "跑道" / "滑行道"
- group(2) = "2" / "19"

然后在第72-78行重组：
```python
if len(match.groups()) == 2:
    prefix, suffix = match.group(1), match.group(2)
    full_match = match.group(0)
    has_space = ' ' in full_match or '_' in full_match
    entities["position"] = f"{prefix}{' ' if has_space else ''}{suffix}"
```

这会生成：
- 输入"跑道2" → 输出"跑道2"（正确，因为原文没有空格）
- 输入"滑行道19" → 输出"滑行道19"（正确）

**但是**，这里有一个问题：如果用户在其他文本中间输入位置（如"我在跑道2 发动机关闭"），实体提取可能只提取到"2"而不是"跑道2"。

2. **Checklist更新逻辑问题**

`update_checklist`函数（第176行）逻辑：
```python
def update_checklist(incident: Dict[str, Any], base_checklist: Dict[str, bool] = None) -> Dict[str, bool]:
    if base_checklist:
        return {k: incident.get(k) is not None for k in base_checklist.keys()}
```

这个逻辑是正确的：只要`incident[k]`不为None，就标记为已收集。

**但是**，问题在于`smart_ask.py`的`get_missing_fields`函数（第47-55行）：
```python
def get_missing_fields(incident: Dict[str, Any], checklist: Dict[str, bool]) -> List[str]:
    required_fields = ["fluid_type", "position", "engine_status", "continuous"]
    missing = []
    for field in required_fields:
        value = incident.get(field)
        is_collected = checklist.get(field, False)
        if not is_collected or value is None:  # ⚠️ 问题在这里！
            missing.append(field)
    return missing
```

这个条件是"或"：`not is_collected or value is None`

意味着：
- 即使`incident["position"]`有值（如"跑道2"），
- 但如果`checklist["position"]`为False（未标记为已收集），
- 仍然会被认为是缺失字段！

**根本原因：**
- **可能性1**：实体提取确实提取到了"跑道2"，但checklist没有正确更新
- **可能性2**：实体提取失败，incident["position"]仍为None

需要检查input_parser节点是否正确调用了`update_checklist`。

---

### 问题2：P2字段被误认为必填

**代码位置：** `agent/nodes/reasoning.py` 或 LLM生成的思考

**问题原因：**

从日志看到的思考：
```
[思考] 当前已收集了所有P1必填字段，但Checklist中还有3个次要字段需要收集：
       aircraft_reg（航空器注册号）、reported_by（报告人）和discovery_method（发现方式）。
```

这是**LLM自己的理解**，不是代码逻辑强制的。

LLM看到了：
1. 状态中的`checklist`字段包含了所有字段（P1+P2）
2. LLM认为"Checklist中还有未收集的字段，应该继续询问"

**但是**，这违反了设计原则：
- P1字段是**必填**的，未收集完成不能进行风险评估
- P2字段是**可选**的，不影响风险评估

**根本原因：**
- Prompt中没有明确告诉LLM：P2字段是可选的，不需要强制收集
- LLM看到checklist中有未收集的字段，就认为应该继续询问

---

## 修复方案

### 修复1：改进位置实体提取和Checklist更新

**文件：** `agent/nodes/input_parser.py`

**修复点1：增强位置匹配的鲁棒性**

在第82-96行，当没有匹配到位置时，尝试更多模式：

```python
# 如果没提取到位置，尝试匹配纯数字（可能是机位号）
if "position" not in entities:
    text_stripped = text.strip()

    # 1. 纯数字2-3位（如 "234", "501"）
    if re.match(r'^\d{2,3}$', text_stripped):
        entities["position"] = text_stripped

    # 2. 用户只回答了位置类型和数字（如"跑道2"、"滑行道19"）
    elif re.match(r'^(跑道|滑行道|机位)\s*\d+', text_stripped):
        entities["position"] = text_stripped

    # 3. 用户在一句话中提到了位置（如"我在跑道2，发动机关闭"）
    else:
        # 尝试匹配跑道/滑行道+数字（不要求前后有特定词汇）
        match = re.search(r'(跑道|滑行道|机位|TWY|RWY)[_\s]?([A-Z]?\d+)', text)
        if match:
            prefix, suffix = match.group(1), match.group(2)
            entities["position"] = f"{prefix}{suffix}"  # 不加空格，保持紧凑
```

**修复点2：确保Checklist正确更新**

检查`input_parser_node`函数（需要读取完整文件）是否在提取实体后正确调用了`update_checklist`。

应该在提取后立即更新：
```python
def input_parser_node(state: AgentState) -> AgentState:
    user_message = state["messages"][-1]["content"]

    # 提取实体
    extracted = extract_entities(user_message)

    # 更新incident
    incident = state.get("incident", {})
    incident.update(extracted)
    state["incident"] = incident

    # ⚠️ 关键：立即更新checklist
    state["checklist"] = update_checklist(incident, state.get("checklist"))

    # ... 其他逻辑
    return state
```

**修复点3：改进`get_missing_fields`逻辑**

**文件：** `tools/information/smart_ask.py`

将第47-55行的逻辑改为"与"：

```python
def get_missing_fields(incident: Dict[str, Any], checklist: Dict[str, bool]) -> List[str]:
    """获取未收集的必填字段"""
    required_fields = ["fluid_type", "position", "engine_status", "continuous"]
    missing = []
    for field in required_fields:
        value = incident.get(field)
        is_collected = checklist.get(field, False)

        # ⚠️ 修复：改为"与"逻辑
        # 只有当值为None **且** checklist未标记为已收集时，才认为缺失
        if value is None and not is_collected:
            missing.append(field)

    return missing
```

或者更严格的版本（推荐）：

```python
def get_missing_fields(incident: Dict[str, Any], checklist: Dict[str, bool]) -> List[str]:
    """获取未收集的必填字段"""
    required_fields = ["fluid_type", "position", "engine_status", "continuous"]
    missing = []
    for field in required_fields:
        value = incident.get(field)

        # ⚠️ 修复：只要incident中有值（不为None），就认为已收集
        # 不再依赖checklist的标记（因为可能更新不及时）
        if value is None:
            missing.append(field)

    return missing
```

---

### 修复2：明确P1/P2字段区分

**文件：** `agent/nodes/reasoning.py` 或 `scenarios/oil_spill/prompt.yaml`

**修复方案1：在Prompt中明确说明**

在场景Prompt中添加：

```yaml
# scenarios/oil_spill/prompt.yaml

system_prompt: |
  你是机场机坪应急响应专家 Agent，专门处理漏油事件...

  ## 信息收集优先级

  **P1字段（必须收集）：**
  - fluid_type（油液类型）
  - position（事发位置）
  - engine_status（发动机状态）
  - continuous（是否持续滴漏）

  ⚠️ **重要**：只有P1字段全部收集完成后，才能进行风险评估！

  **P2字段（可选收集）：**
  - leak_size（泄漏面积）
  - aircraft_reg（航空器注册号）
  - flight_no（航班号）
  - reported_by（报告人）
  - discovery_method（发现方式）

  ⚠️ **重要**：P2字段是补充信息，不影响风险评估。如果用户未提供，不需要强制询问，可以直接进行风险评估。

  ## 工作流程

  1. **信息收集阶段**：使用`smart_ask`工具收集P1字段
  2. **风险评估阶段**：P1字段收集完成后，立即调用`assess_risk`
  3. **后续处理**：根据风险等级执行相应操作

  ⚠️ **禁止**在P1收集完成后，继续询问P2字段！应该立即进行风险评估。
```

**修复方案2：在代码中强制逻辑**

在`reasoning.py`的prompt构建函数中，添加明确的指令：

```python
def build_scenario_prompt(state, scenario, tools_desc):
    # ... 现有逻辑

    # 添加明确的Checklist状态说明
    checklist = state.get("checklist", {})
    p1_fields = ["fluid_type", "position", "engine_status", "continuous"]
    p1_complete = all(checklist.get(f, False) for f in p1_fields)

    if p1_complete:
        prompt += "\n\n⚠️ **重要提示**：所有P1必填字段已收集完成，请立即调用`assess_risk`工具进行风险评估，不要继续询问P2字段！\n"
    else:
        missing_p1 = [f for f in p1_fields if not checklist.get(f, False)]
        prompt += f"\n\n⚠️ **当前状态**：P1字段缺失：{missing_p1}，请使用`smart_ask`继续收集。\n"

    return prompt
```

**修复方案3：修改`smart_ask`工具，只询问P1字段**

**文件：** `tools/information/smart_ask.py`

确保`get_missing_fields`只返回P1字段：

```python
def get_missing_fields(incident: Dict[str, Any], checklist: Dict[str, bool]) -> List[str]:
    """获取未收集的必填字段（仅P1）"""
    # ⚠️ 修复：只检查P1字段，P2字段不在此处理
    required_fields = ["fluid_type", "position", "engine_status", "continuous"]
    missing = []
    for field in required_fields:
        value = incident.get(field)
        if value is None:
            missing.append(field)
    return missing
```

并在工具返回时明确说明：

```python
def execute(self, state: Dict[str, Any], inputs: Dict[str, Any] = None) -> Dict[str, Any]:
    incident = state.get("incident", {})
    checklist = state.get("checklist", {})

    # 获取缺失字段（仅P1）
    missing = get_missing_fields(incident, checklist)

    if not missing:
        return {
            "observation": "所有P1必填字段已收集完成，可以进行风险评估",  # ⚠️ 明确说明
            "missing_fields": [],
            "question": None,
            "ready_for_assessment": True,
            "messages": [],
        }

    # ... 其他逻辑
```

---

## 修复优先级

### P0（立即修复）

1. ✅ **修复`get_missing_fields`逻辑**（`smart_ask.py`）
   - 改为只检查`value is None`，不依赖checklist标记
   - 预计修复时间：5分钟

2. ✅ **增强位置实体提取**（`input_parser.py`）
   - 改进正则匹配逻辑，支持"跑道2"、"滑行道19"等格式
   - 预计修复时间：10分钟

### P1（短期修复）

3. ✅ **在Prompt中明确P1/P2区分**（`prompt.yaml`）
   - 明确告诉LLM：P1收集完成后立即评估，不要询问P2
   - 预计修复时间：10分钟

### P2（长期优化）

4. ⚠️ **重构Checklist管理逻辑**
   - 分离P1和P2的状态管理
   - 添加`p1_complete`和`p2_complete`标志
   - 预计修复时间：30分钟

---

## 测试用例

### 测试用例1：位置提取

**输入：**
```
机长: 跑道2 发动机关闭
```

**期望：**
- `incident["position"]` = "跑道2"
- `incident["engine_status"]` = "STOPPED"
- `checklist["position"]` = True
- `checklist["engine_status"]` = True

**输入：**
```
机长: 滑行道19
```

**期望：**
- `incident["position"]` = "滑行道19"
- `checklist["position"]` = True
- 不再询问位置

---

### 测试用例2：P1完成后不询问P2

**场景：**
```
用户: 川航3349，滑油泄漏，持续滴漏，发动机关闭，在501机位
```

**期望行为：**
1. 提取P1字段：fluid_type=OIL, continuous=True, engine_status=STOPPED, position=501机位, flight_no=3U3349
2. 检查P1完成：✓
3. **直接调用`assess_risk`**，而不是询问P2字段（aircraft_reg, reported_by等）

**不期望行为（当前Bug）：**
1. 提取P1字段 ✓
2. 询问："还有3个次要字段需要收集：aircraft_reg..."  ✗

---

## 实施计划

1. **立即修复**（10分钟）：
   - 修改`smart_ask.py`的`get_missing_fields`
   - 测试位置提取

2. **短期优化**（20分钟）：
   - 修改`prompt.yaml`添加P1/P2说明
   - 增强位置正则匹配

3. **验证测试**（10分钟）：
   - 运行测试用例1和2
   - 确认问题解决

---

## 总结

这两个问题的根源都是**状态管理和逻辑判断**：
1. **位置重复提问**：`get_missing_fields`的逻辑过于严格，即使有值也可能被认为缺失
2. **P1/P2不一致**：LLM没有被明确告知P2是可选的，误认为需要全部收集

修复后：
- 位置提取更鲁棒，支持多种输入格式
- P1收集完成后立即评估，不再询问P2
- 系统行为更符合设计预期
