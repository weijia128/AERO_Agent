# 场景字段过滤验证报告

## 问题1：无论实体提取LLM是否参与都不会有类似的bug

### ✅ 已验证并修复

修复涵盖**两种模式**：

#### 模式1：`ENABLE_SEMANTIC_UNDERSTANDING=false`（默认模式）
- **路径**: `extract_entities_hybrid` → 混合提取（正则+LLM）
- **修复位置**: `input_parser.py:661-683`
- **过滤机制**:
  ```python
  # 获取当前场景允许的字段
  allowed_fields = set(_get_scenario_field_keys(scenario_type) or [])
  allowed_fields.update(['flight_no', 'flight_no_display', 'position', ...])

  # 只合并属于当前场景的字段
  for key, value in extracted.items():
      if value is not None and key in allowed_fields:
          current_incident[key] = value
      elif value is not None and key not in allowed_fields:
          logger.warning(f"字段 {key} 不属于场景 {scenario_type}，已忽略")
  ```
- **测试**: `test_fod_scenario_integration.py` ✅ 通过

#### 模式2：`ENABLE_SEMANTIC_UNDERSTANDING=true`（语义理解模式）
- **路径**: `understand_conversation` → 语义理解提取
- **修复位置**: `input_parser.py:638-650`
- **过滤机制**:
  ```python
  # 合并信息并记录潜在冲突 - 添加字段过滤
  for key, value in extracted.items():
      # 检查字段是否属于当前场景
      if key not in allowed_field_keys and value is not None:
          logger.warning(f"语义理解提取的字段 {key} 不属于场景 {scenario_type}，已忽略")
          continue

      # ... 合并逻辑
  ```
- **测试**: `test_semantic_understanding_field_filtering.py` ✅ 通过

### 字段过滤的三道防线

1. **旧state字段复制时过滤** (`input_parser.py:610-614`)
   - 从上一轮state复制字段时，只复制属于当前场景的字段

2. **实体提取结果合并时过滤** (`input_parser.py:642-650`, `668-671`)
   - 两种模式都添加了字段检查

3. **规范化工具结果合并时过滤** (`input_parser.py:674-680`)
   - RadiotelephonyNormalizerTool的结果也要检查

## 问题2：航空读法目前的流程是否被改变

### ✅ 已优化，行为更合理

#### 改变内容

**修改前**:
- 所有用户输入都进行LLM规范化（包括"已移除"、"金属"等简短回答）

**修改后**:
- 智能判断是否需要LLM规范化
- 规则: `包含航空读法词 OR (包含航空特征词 AND 长度>5)`

```python
# 检查是否需要LLM规范化
has_radiotelephony = any(kw in text for kw in ["洞", "幺", "两", "拐", "五"])
has_aviation_keywords = any(kw in text for kw in ["跑道", "机位", "滑行道", "川航", "国航", ...])

needs_normalization = (
    has_radiotelephony or
    (has_aviation_keywords and len(text) > 5)
)
```

#### 行为对比

| 输入示例 | 修改前 | 修改后 | 说明 |
|---------|-------|-------|------|
| "已移除" | ⚠️ 触发LLM | ✅ 跳过 | 避免错误提取对话历史中的信息 |
| "金属" | ⚠️ 触发LLM | ✅ 跳过 | 简短回答不需要规范化 |
| "跑道幺八右" | ✅ 触发LLM | ✅ 触发LLM | 包含航空读法词 |
| "川航三幺拐拐" | ✅ 触发LLM | ✅ 触发LLM | 包含航空读法词 |
| "跑道18R发现异物" | ✅ 触发LLM | ✅ 触发LLM | 包含航空关键词且长度>5 |
| "国航1234" | ✅ 触发LLM | ✅ 触发LLM | 包含航空公司名称且长度>5 |
| "501机位漏油" | ✅ 触发LLM | ✅ 触发LLM | 包含航空关键词且长度>5 |
| "501" | ⚠️ 触发LLM | ✅ 跳过 | 纯数字机位不需要LLM规范化 |

#### 优势

1. **修复bug**: 避免简短回答触发LLM导致错误提取
2. **性能优化**: 减少不必要的LLM调用
3. **保留功能**: 所有需要规范化的航空读法输入仍然正常工作

#### 不影响的功能

基础航空读法规范化（第一步）**不受影响**：
```python
normalized_message = normalize_radiotelephony_text(user_message)
# 基于规则的转换：洞→0, 幺→1, 拐→7 等
```

只是优化了第二步的**LLM深度规范化**触发条件。

## 测试覆盖

### 单元测试
- ✅ `test_scenario_locking.py` - 场景锁定和字段提取
- ✅ `test_fod_scenario_integration.py` - FOD场景完整流程
- ✅ `test_semantic_understanding_field_filtering.py` - 语义理解字段过滤

### 测试结果
```
tests/agent/test_scenario_locking.py::test_get_scenario_field_keys PASSED
tests/agent/test_scenario_locking.py::test_build_field_descriptions PASSED
tests/agent/test_scenario_locking.py::test_extract_entities_hybrid_field_filtering PASSED
tests/agent/test_scenario_locking.py::test_scenario_field_isolation PASSED
tests/agent/test_fod_scenario_integration.py::test_fod_scenario_conversation_flow PASSED
tests/agent/test_semantic_understanding_field_filtering.py::test_semantic_understanding_field_filtering PASSED

6 passed in 9.47s
```

## 结论

✅ **问题1**: 两种模式（ENABLE_SEMANTIC_UNDERSTANDING=true/false）都已添加字段过滤，不会有类似bug
✅ **问题2**: 航空读法流程优化更合理，必要功能保留，性能提升

所有关键场景已通过测试验证。
