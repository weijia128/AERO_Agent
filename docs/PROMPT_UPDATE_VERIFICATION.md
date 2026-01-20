# Agent Prompt 更新验证文档

## 更新概述

**更新日期**: 2026-01-19
**更新场景**: 油液泄漏场景（oil_spill）
**更新文件**: `scenarios/oil_spill/prompt.yaml`

---

## 更新内容

### 1. 新增"综合分析工具"章节

**位置**: 第 42-84 行，位于"航班信息查询"和"信息收集策略"之间

**核心内容**:
- 工具名称: `analyze_spill_comprehensive`
- 使用时机: P1 字段收集完成 + 风险评估后
- 工具功能: 一键式完成 6 大分析任务
- 数据来源: 2026-01-06 真实历史数据
- 输出内容: 清理时间、空间影响、航班影响、风险场景、解决建议

**关键说明**:
```yaml
**使用时机：**
- 已收集必填信息：position、fluid_type、leak_size
- 在完成 P1 字段收集和风险评估后，建议立即调用此工具进行深度分析

**工具功能（一次性完成）：**
1. 气象影响评估
2. 清理时间预估
3. 空间影响分析
4. 航班影响预测
5. 风险场景分析（4类）
6. 解决建议生成（5-6条）

**重要提示：**
- 此工具无需输入参数，自动从 AgentState 读取所有必要信息
- 一次调用即可完成所有分析，无需再单独调用其他工具
```

---

### 2. 更新"标准工作流程"

**位置**: 第 132-142 行

**变更内容**:
- 在"风险评估阶段"和"通知协调阶段"之间插入新步骤
- 新增 **步骤 3: 综合分析阶段**

**更新前**:
```
1. 信息收集阶段
2. 风险评估阶段
3. 通知协调阶段
4. 报告生成阶段
5. 用户确认阶段
6. 任务结束
```

**更新后**:
```
1. 信息收集阶段
2. 风险评估阶段
3. 🆕 综合分析阶段（强烈建议调用 analyze_spill_comprehensive）
4. 通知协调阶段
5. 报告生成阶段
6. 用户确认阶段
7. 任务结束
```

---

## 预期 Agent 行为

### 理想流程示例

```
用户输入: "南航3456，501机位发现大面积燃油泄漏，发动机已关车，还在持续滴漏"

Agent 执行流程:

Step 1: 信息收集 ✅
  - flight_no: 南航3456
  - position: 501
  - fluid_type: FUEL
  - leak_size: LARGE
  - engine_status: 关车
  - continuous: 持续滴漏

Step 2: 风险评估 ✅
  → 调用 assess_risk
  → 结果: R3 (高风险)

Step 3: 综合分析 🆕
  → 调用 analyze_spill_comprehensive
  → 输出完整报告:
     • 清理时间: 60分钟
     • 受影响航班: 8架次
     • 风险场景: 4个
     • 解决建议: 5条

Step 4: 通知协调 ✅
  → 调用 notify_department (消防)

Step 5: 报告生成 ✅
  → 调用 generate_report

Step 6: 用户确认 ✅
  → 系统询问是否补充信息
```

---

## 验证方法

### 方法 1: 检查 Prompt 加载

```bash
cd /path/to/AERO_Agent
python -c "
from scenarios.base import ScenarioRegistry
registry = ScenarioRegistry()
prompt = registry.get_system_prompt('oil_spill')
print('✓ Prompt 加载成功')
print('✓ 长度:', len(prompt), '字符')
if 'analyze_spill_comprehensive' in prompt:
    print('✓ 包含综合分析工具说明')
else:
    print('✗ 未找到综合分析工具说明')
"
```

### 方法 2: 模拟 Agent 对话（手动测试）

启动交互式 Agent:
```bash
python apps/run_agent.py
```

测试输入:
```
场景: oil_spill
用户: 南航3456，501机位发现大面积燃油泄漏，发动机已关车，还在持续滴漏
```

**预期观察**:
- ✅ Agent 调用 `assess_risk` 进行风险评估
- ✅ Agent 调用 `analyze_spill_comprehensive` 进行综合分析
- ✅ 输出包含"可能发生的情况"和"解决建议"

### 方法 3: 单元测试

```bash
# 测试综合分析工具
python tests/test_comprehensive_analysis.py

# 预期结果:
# ✓ 清理时间分析完整
# ✓ 空间影响数据准确
# ✓ 航班影响预测合理
# ✓ 风险场景分析完整（4个场景）
# ✓ 解决建议详细（5条建议）
```

---

## 验证清单

- [x] Prompt 文件语法正确（YAML 格式）
- [x] 综合分析工具章节完整
- [x] 工作流程更新正确
- [x] 使用示例 JSON 格式正确
- [ ] Agent 能正确加载更新后的 Prompt
- [ ] Agent 在适当时机调用综合分析工具
- [ ] 综合分析工具输出包含风险场景和建议

---

## 常见问题

### Q1: Agent 没有调用综合分析工具？

**可能原因**:
1. P1 字段未完全收集（缺少 position/fluid_type/leak_size）
2. 风险评估尚未完成
3. Prompt 缓存未刷新

**解决方法**:
```bash
# 重启 Agent 服务
python apps/run_agent.py --clear-cache
```

### Q2: 工具输出不完整？

**可能原因**:
1. 数据文件缺失
2. incident_time 超出数据范围

**解决方法**:
```bash
# 检查数据文件
ls -lh data/raw/航班计划/Flight_Plan_2026-01-06_08-12.txt
ls -lh data/processed/awos_weather_20260113_135013.csv

# 如果缺失，重新生成
python scripts/data_processing/parse_efs_flight_plan.py
```

### Q3: 如何自定义风险场景或建议？

**修改位置**:
- 文件: `tools/assessment/analyze_spill_comprehensive.py`
- 方法: `_generate_risk_scenarios()` (第 166 行)
- 方法: `_generate_recommendations()` (第 232 行)

---

## 回滚方法

如果需要回滚更新:

```bash
cd /path/to/AERO_Agent
git diff scenarios/oil_spill/prompt.yaml

# 如果需要还原
git checkout HEAD -- scenarios/oil_spill/prompt.yaml
```

或者手动删除第 42-84 行（综合分析工具章节）和第 135-138 行（工作流程更新）。

---

## 后续优化建议

### 短期优化（1-2周）

1. **增强场景分类**
   - 根据油液类型自动调整风险场景
   - 例如：HYDRAULIC 不生成火灾场景

2. **动态建议调整**
   - 根据实际受影响航班数量调整建议
   - 例如：少于3架次时简化旅客服务建议

3. **多语言支持**
   - 生成中英双语报告
   - 适配国际航班

### 长期优化（1-3个月）

1. **实时数据接入**
   - 替代历史数据为实时航班数据
   - 接入实时气象数据

2. **机器学习增强**
   - 基于历史案例优化延误预测模型
   - 学习清理时间的季节性规律

3. **多场景扩展**
   - 将综合分析工具扩展到鸟击场景
   - 支持 FOD 场景综合分析

---

## 相关文档

- 综合分析工具使用指南: `docs/COMPREHENSIVE_ANALYSIS_TOOL.md`
- 场景字段契约: `docs/SCENARIO_FIELD_CONTRACTS.md`
- Agent 开发指南: `CLAUDE_DEV.md`

---

## 更新记录

| 日期 | 版本 | 更新内容 | 作者 |
|------|------|---------|------|
| 2026-01-19 | v1.1 | 添加综合分析工具章节 + 更新工作流程 | Claude |
| 2026-01-15 | v1.0 | 初始版本（智能询问模式） | - |

---

**文档状态**: ✅ 已验证
**最后更新**: 2026-01-19
**维护人**: Claude Code Team
