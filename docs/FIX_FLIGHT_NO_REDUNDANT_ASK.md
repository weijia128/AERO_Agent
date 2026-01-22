# 修复：航班号重复询问问题

**日期**: 2026-01-22
**问题**: 系统在已提取到航班号后仍重复询问"报告你机号"
**影响**: 违反航空通话规范，用户体验差

## 问题分析

### 根本原因

1. **Checklist 状态未被使用**: `get_missing_fields()` 函数虽然接收了 `checklist` 参数，但完全没有使用它，只检查 `incident` 字段的值
2. **航班号双字段未同步**: 系统使用 `flight_no` (ICAO格式) 和 `flight_no_display` (显示格式) 两个字段，但 `update_checklist()` 只检查 `flight_no`

### 问题流程

```
用户输入: "东航两三九两报告紧急情况..."
    ↓
input_parser 提取: flight_no='MU2392', flight_no_display='东航2392'
    ↓
update_checklist() 只检查 incident.get("flight_no")
    ↓
checklist["flight_no"] = True ✅ (正确)
    ↓
smart_ask 调用 get_missing_fields()
    ↓
get_missing_fields() 忽略 checklist，只检查 incident
    ↓
❌ 错误：因为某些代码路径下 incident["flight_no"] 可能为 None
    ↓
错误地询问："报告你机号"
```

## 修复方案

### 1. 修复 `update_checklist()` (input_parser.py:345-372)

**修改前**:
```python
def update_checklist(incident, base_checklist=None):
    if base_checklist:
        return {k: incident.get(k) is not None for k in base_checklist.keys()}
    # ...
```

**修改后**:
```python
def update_checklist(incident, base_checklist=None):
    """根据事件信息更新 Checklist 状态（保持场景字段）

    特殊处理：
    - flight_no: 检查 flight_no 或 flight_no_display 任一存在即标记为已收集
    """
    if base_checklist:
        result = {}
        for k in base_checklist.keys():
            # 特殊处理：航班号检查两个字段
            if k == "flight_no":
                result[k] = bool(incident.get("flight_no") or incident.get("flight_no_display"))
            else:
                result[k] = incident.get(k) is not None
        return result
    # ...
```

### 2. 修复 `get_missing_fields()` (smart_ask.py:67-94)

**修改前**:
```python
def get_missing_fields(incident, checklist, scenario_type="oil_spill"):
    required_fields = _resolve_required_fields(scenario_type, incident)
    missing = []
    for field in required_fields:
        value = incident.get(field)  # ❌ 忽略 checklist 参数
        if value in [None, ""]:
            missing.append(field)
    return missing
```

**修改后**:
```python
def get_missing_fields(incident, checklist, scenario_type="oil_spill"):
    """获取未收集的必填字段（按场景配置）。

    优先使用 checklist 状态判断字段是否已收集，确保与 input_parser 更新的状态一致。
    """
    required_fields = _resolve_required_fields(scenario_type, incident)
    missing = []
    for field in required_fields:
        # ✅ 优先检查 checklist 状态（input_parser 已更新）
        if checklist.get(field, False):
            continue

        # Fallback: 如果 checklist 中没有该字段，检查 incident 的值
        if field == "flight_no":
            flight_no = incident.get("flight_no") or incident.get("flight_no_display")
            if not flight_no:
                missing.append(field)
        else:
            value = incident.get(field)
            if value in [None, ""]:
                missing.append(field)
    return missing
```

### 3. 航空通话规范前缀保持不变

`build_combined_question()` 已经正确实现了航班号前缀添加逻辑，无需修改。

## 测试覆盖

创建了 4 个单元测试 (`tests/tools/test_smart_ask_flight_no.py`):

1. ✅ `test_flight_no_extracted_should_not_ask_again`: 航班号已提取时不重复询问
2. ✅ `test_smart_ask_with_flight_no_should_have_callsign_prefix`: 问题包含航班号前缀
3. ✅ `test_flight_no_display_only_should_also_mark_as_collected`: 只有 display 格式也标记为已收集
4. ✅ `test_no_flight_no_should_ask`: 确实缺失时正确询问

运行结果：**4/4 通过**

## 验证结果

### 修复前
```
用户: 东航两三九两报告紧急情况，右侧发动机有滑油泄漏
系统: 已收集信息: 航班号=MU2392, 油液类型=OIL, 持续泄漏=True
系统: ❌ 报告你机号  （重复询问）
```

### 修复后
```
用户: 东航两三九两报告紧急情况，右侧发动机有滑油泄漏
系统: 已收集信息: 航班号=MU2392, 油液类型=OIL, 持续泄漏=True
系统: ✅ 东航2392，目前飞机的大概位置在哪？停机位还是滑行道？ 发动机当前状态？运转还是关车？
```

## 文件变更

| 文件 | 变更内容 | 行数 |
|------|---------|------|
| `agent/nodes/input_parser.py` | 修复 `update_checklist()` 函数 | 345-372 |
| `tools/information/smart_ask.py` | 修复 `get_missing_fields()` 函数 | 67-94 |
| `tests/tools/test_smart_ask_flight_no.py` | 新增单元测试 | +102 |
| `docs/FIX_FLIGHT_NO_REDUNDANT_ASK.md` | 本文档 | +170 |

## 关键要点

1. **Checklist 是真相源 (Source of Truth)**: `input_parser` 更新 checklist 后，所有下游工具都应该优先检查 checklist 状态
2. **双字段同步**: `flight_no` 和 `flight_no_display` 必须同步检查，任一存在即标记为已收集
3. **优先级顺序**: checklist > incident 字段检查 > fallback 逻辑
4. **航空规范**: 所有回复必须包含航班号前缀（符合 ICAO 通话规范）

## 后续改进建议

1. 考虑将 `flight_no_display` 和 `flight_no` 合并为单一字段，避免同步问题
2. 在 `update_checklist()` 中添加更多特殊字段处理逻辑（如 `position` / `position_display`）
3. 增强 checklist 状态的可观测性（日志、调试输出）

---

## 补充修复：LangGraph 状态传递问题

**日期**: 2026-01-22
**问题**: 即使 checklist 和 incident 逻辑正确，tool_executor 仍然收不到这些状态

### 根本原因

LangGraph 0.2.x 使用 `Dict[str, Any]` 作为状态类型时，不会自动合并节点返回值。每个节点只返回它修改的字段，导致其他字段无法传递到下游节点。

**Debug 日志显示**:
```
tool_executor 收到 state keys: ['current_thought', 'current_action', ...]
tool_executor 收到 checklist: None
tool_executor 收到 incident: None
```

### 修复方案

在 `reasoning_node` 中添加 `_build_return_state()` 辅助函数，确保关键字段被传递：

```python
def _build_return_state(state: AgentState, updates: Dict[str, Any]) -> Dict[str, Any]:
    """构建返回状态，确保关键字段被传递。"""
    critical_fields = [
        "session_id", "scenario_type", "incident", "checklist",
        "messages", "risk_assessment", "spatial_analysis", ...
    ]

    result = {}
    for field in critical_fields:
        if field in state:
            result[field] = state[field]

    result.update(updates)
    return result
```

### 修改的函数

- `reasoning_node()` 中所有 return 语句都使用 `_build_return_state()` 包装

### 测试结果

```
tests/tools/test_smart_ask_flight_no.py::test_flight_no_extracted_should_not_ask_again PASSED
tests/tools/test_smart_ask_flight_no.py::test_smart_ask_with_flight_no_should_have_callsign_prefix PASSED
tests/tools/test_smart_ask_flight_no.py::test_flight_no_display_only_should_also_mark_as_collected PASSED
tests/tools/test_smart_ask_flight_no.py::test_no_flight_no_should_ask PASSED
```

### 长期改进建议

考虑将 `AgentState` 从 `Dict[str, Any]` 类型别名改为 `TypedDict` + `Annotated` reducers，这是 LangGraph 推荐的状态管理方式，可以自动处理状态合并。
