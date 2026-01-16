# AERO Agent 优化规划文档

> 生成日期：2026-01-16
> 目标：为机坪管制员的特情事件提供智能辅助

---

## 目录

- [项目目标](#项目目标)
- [当前状态评估](#当前状态评估)
- [目标 1：检查工单生成优化](#目标-1检查工单生成优化)
- [目标 2：辅助建议系统优化](#目标-2辅助建议系统优化)
- [实施路线图](#实施路线图)
- [推荐首先实施的任务](#推荐首先实施的任务)

---

## 项目目标

### 核心目标

1. **根据特情情况生成检查工单**
   - 结构化工单输出（JSON/PDF/Excel）
   - 场景感知的动态检查项
   - 现场作业指导自动生成
   - 责任单位和优先级自动分配

2. **提供有价值的辅助建议**
   - 整合机场拓扑数据
   - 结合航班计划分析影响
   - 利用航迹数据优化绕行
   - 基于气象数据调整处置策略

---

## 当前状态评估

### 总体完成度

| 目标功能 | 当前完成度 | 核心差距 |
|---------|-----------|---------|
| **检查工单生成** | 60% | 输出为纯文本，缺乏结构化；检查项静态，不随场景变化 |
| **辅助建议系统** | 45% | 数据资源丰富但整合度<30% |

### 数据资源利用现状

| 数据类型 | 文件位置 | 大小 | 利用率 | 问题 |
|---------|---------|------|-------|------|
| **拓扑数据** | `data/spatial/airport_topology.json` | - | 100% | ✓ 完全利用 |
| **气象数据** | `data/processed/awos_weather_*.csv` | 318 KB | 5% | 仅作为工具，不影响建议 |
| **航班计划** | `data/raw/航班计划/Log_*.txt` | - | 10% | 仅展示，不用于决策 |
| **航迹数据** | `data/raw/航迹数据/MCR_*.` | 560 MB | 0% | 完全未集成 |
| **飞行规程** | `tools/knowledge/search_regulations.py` | 模拟 | 30% | 模拟知识库 |

---

## 目标 1：检查工单生成优化

### 当前实现分析

#### 已完成的部分 ✓

1. **报告生成框架**
   - `agent/nodes/output_generator.py` (990 行) 包含完整的输出生成逻辑
   - 使用 Jinja2 模板渲染 (`agent/templates/base_report.md.j2`)
   - 生成的报告包含标题、事件摘要、风险等级、处置过程等

2. **检查单数据模型**
   - `AgentState` 包含 checklist、incident、risk_assessment、actions_taken 等字段
   - `generate_checklist_items()` 函数生成三类检查项

3. **协调单位管理**
   - `generate_coordination_units()` 生成 5 个协调单位
   - 记录通知状态、时间、优先级

4. **事件摘要生成**
   - LLM 生成版本：`_generate_event_summary_with_llm()`
   - 确定性回退版本：`_build_deterministic_summary()`

#### 存在的关键差距 ✗

| 差距 | 描述 | 影响 |
|-----|------|------|
| **工单结构化程度不足** | 报告输出为 Markdown 纯文本，不是结构化工单格式 | 无法与其他系统对接 |
| **现场作业指导缺失** | 没有根据特情自动生成作业步骤 | 管制员需要人工判断 |
| **优先级和责任划分不清** | 缺乏场景特定的责任分配逻辑 | 协调效率低 |
| **检查点覆盖不完整** | 当前仅有 9 项检查，缺少安全措施、环保合规等 | 流程不完整 |
| **与场景配置不关联** | 未读取 `scenarios/<scenario>/checklist.yaml` | 无法差异化处理 |

### 改进方案

#### 阶段 1：工单结构化改造（优先级 P0）

**目标架构**：

```
┌─────────────────────────────────────────────────────────┐
│ 当前状态                                                │
├─────────────────────────────────────────────────────────┤
│ output_generator.py                                     │
│   ├─ 生成 Markdown 文本报告                             │
│   ├─ 检查项为静态占位符 (☐ 是  ☐ 否)                    │
│   └─ 未读取 scenarios/<scenario>/checklist.yaml        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 目标状态                                                │
├─────────────────────────────────────────────────────────┤
│ output_generator.py                                     │
│   ├─ 生成结构化 JSON + 可视化报告                       │
│   ├─ 根据场景动态加载检查项模板                         │
│   ├─ 基于特情自动生成：                                 │
│   │   ├─ 现场作业指导步骤                               │
│   │   ├─ 责任单位和优先级                               │
│   │   └─ 装备物资清单                                   │
│   └─ 输出格式: JSON / PDF / Excel                       │
└─────────────────────────────────────────────────────────┘
```

**具体任务**：

| 任务 ID | 任务 | 文件 | 说明 |
|--------|-----|------|------|
| 1.1 | 定义工单数据模型 | `agent/models/work_order.py` (新建) | 创建 `WorkOrder` TypedDict |
| 1.2 | 加载场景检查项 | `agent/nodes/output_generator.py` | 读取 `scenarios/{scenario}/checklist.yaml` |
| 1.3 | 生成作业指导 | `tools/action/generate_work_instructions.py` (新建) | 基于流体类型+风险等级生成 |
| 1.4 | 责任分配引擎 | `tools/action/assign_responsibilities.py` (新建) | 自动分配责任单位和优先级 |

#### 阶段 2：场景感知检查项（优先级 P1）

**工单模板设计**：

```yaml
# scenarios/oil_spill/work_order_template.yaml (新建)
work_order:
  phases:
    - name: "现场安全控制"
      priority: 1
      checklist:
        - id: "SC001"
          item: "确认发动机已关闭"
          condition: "engine_status == 'RUNNING'"  # 条件触发
          assignee: "机务"
          required_equipment: ["灭火器", "接地线"]
        - id: "SC002"
          item: "设置安全警戒区"
          radius_rule: "risk_level"  # 动态计算
          assignee: "安检"

    - name: "清污处置"
      priority: 2
      checklist:
        - id: "CL001"
          item: "铺设吸油毡"
          quantity_rule: "leak_size * 2"  # 动态计算
          assignee: "清污"
        - id: "CL002"
          item: "启动防爆泵抽吸"
          condition: "fluid_type == 'FUEL' AND leak_size == 'LARGE'"
          assignee: "消防"

    - name: "恢复验收"
      priority: 3
      checklist:
        - id: "RV001"
          item: "地面摩擦系数检测"
          threshold: ">=0.5"
          assignee: "场务"
```

**具体任务**：

| 任务 ID | 任务 | 说明 |
|--------|-----|------|
| 2.1 | 创建油液泄漏工单模板 | `scenarios/oil_spill/work_order_template.yaml` |
| 2.2 | 创建鸟击工单模板 | `scenarios/bird_strike/work_order_template.yaml` |
| 2.3 | 实现条件解析器 | 解析 `condition` 字段，动态启用/禁用检查项 |
| 2.4 | 实现数量计算器 | 解析 `quantity_rule` 等动态规则 |

#### 阶段 3：工单输出多格式（优先级 P2）

| 任务 ID | 任务 | 说明 |
|--------|-----|------|
| 3.1 | JSON 结构化输出 | 标准工单 JSON Schema |
| 3.2 | PDF 报告生成 | 使用 `reportlab` 或 `weasyprint` |
| 3.3 | Excel 检查单 | 使用 `openpyxl` 生成可填写的检查表 |

---

## 目标 2：辅助建议系统优化

### 各模块实现完整度

| 模块 | 实现状态 | 完整度 | 主要问题 |
|------|---------|-------|--------|
| **拓扑分析** (`tools/spatial/`) | 部分实现 | 70% | BFS 算法完整，但缺乏风险热点分析 |
| **航班计划查询** (`flight_plan_lookup.py`) | 完整实现 | 95% | 仅用于展示，不影响决策 |
| **气象数据** (`get_weather.py`) | 完整实现 | 95% | 数据完整，但在建议中的使用有限 |
| **航迹数据处理** (`parse_trajectory.py`) | 存在但未集成 | 20% | 有解析器但未与主线程集成 |
| **航班影响预测** (`predict_flight_impact.py`) | 部分实现 | 50% | 框架完整但算法简单，硬编码时间 |

### 详细分析

#### 1. 拓扑分析（完整度 70%）

**已实现**：
- ✓ `topology_loader.py`：完整的图数据加载和 BFS 算法
- ✓ `calculate_impact_zone.py`：基于流体类型的 3 层扩散规则
- ✓ `analyze_position_impact.py`：位置影响严重程度评估
- ✓ 机位、滑行道、跑道分类

**缺失的高价值建议**：
- ✗ 风险热点识别：未分析哪些位置最容易发生泄漏
- ✗ 关键基础设施保护：未强调对消防水栓、排水系统的影响
- ✗ 滑行效率影响：缺乏精细的流量模型
- ✗ 空间约束优化：未建议临时机位/滑行道使用方案

#### 2. 航班计划查询（完整度 95%）

**已实现**：
- ✓ 从 `data/raw/航班计划/Log_4.txt` 查询
- ✓ 支持多种航班号格式
- ✓ 返回完整的航班计划表

**缺失的高价值建议**：
- ✗ 航班优先级排序：未根据国际/国内、VIP 航班等因素建议处置优先级
- ✗ 滑行冲突预警：未分析多航班同时滑行的风险
- ✗ 联程航班风险：未关联后续航班的换机风险
- ✗ 客流影响评估：未估算旅客和行李的中转影响

#### 3. 气象数据（完整度 95%）

**已实现**：
- ✓ 完整的 AWOS 数据处理（温度、风速、能见度、QNH）
- ✓ 位置-时间双索引查询
- ✓ 8 个观测点数据

**缺失的高价值建议**：
- ✗ 风向风速对清污的影响：未建议风向调整清污顺序
- ✗ 能见度与检查方案：未因低能见度调整检查策略
- ✗ 气象窗口预测：未提示何时是最佳清污窗口
- ✗ 冻融风险：未根据温度建议防滑/防冻措施

#### 4. 航迹数据（完整度 20%）

**现状**：
- 原始数据存在：`data/raw/航迹数据/MCR_2026-01-06_*.` (560+ MB)
- 解析器存在：`parse_trajectory.py`
- **完全未与主线程集成**

**缺失的高价值建议**：
- ✗ 历史路径偏差分析
- ✗ 机位接近度分析
- ✗ 滑行时间基准
- ✗ 碰撞风险热点
- ✗ 应急滑行路线建议

#### 5. 航班影响预测（完整度 50%）

**已实现**：
- ✓ 框架完整（PredictFlightImpactTool）
- ✓ 延误规则定义（DELAY_RULES）
- ✓ 严重程度分布统计

**关键问题**：
- ✗ **硬编码时间**（第 102 行）：`current_time = datetime.fromisoformat("2025-10-21 11:00:00")`
- ✗ 简化的延误模型：未考虑航班间隔、跑道容量
- ✗ 缺乏连锁延误：未模拟级联延误效应

### 改进方案

#### 阶段 1：气象数据深度整合（优先级 P0）

**新建文件**：`tools/advisory/weather_impact_advisor.py`

```python
class WeatherImpactAdvisor:
    """
    基于气象数据生成处置建议
    """

    def analyze_cleanup_conditions(self, weather_data: dict, fluid_type: str) -> dict:
        """
        分析清污作业条件

        Returns:
            {
                "wind_advisory": "当前风向东北，建议从下风向开始清污",
                "visibility_advisory": "能见度良好(>5km)，适合全面检查",
                "temperature_advisory": "气温15°C，流体粘度适中，建议立即清理",
                "optimal_window": "未来2小时气象条件稳定，建议立即作业",
                "risk_factors": ["风速>10m/s可能导致油气扩散"]
            }
        """

    def suggest_safety_measures(self, weather_data: dict) -> list:
        """
        生成气象相关安全措施

        Examples:
            - 风速 > 15m/s → "暂停高空作业，注意地面物品固定"
            - 温度 < 5°C → "注意防滑，准备除冰剂"
            - 能见度 < 1km → "启用辅助照明，缩小作业范围"
        """
```

**具体任务**：

| 任务 ID | 任务 | 说明 |
|--------|-----|------|
| W1.1 | 创建气象建议引擎 | `tools/advisory/weather_impact_advisor.py` |
| W1.2 | 定义气象-建议规则 | 风向、风速、温度、能见度的决策规则 |
| W1.3 | 集成到报告生成 | 在 `output_generator.py` 中调用 |
| W1.4 | 添加气象自动触发 | 在 `reasoning.py` 中自动查询气象 |

#### 阶段 2：航班影响智能分析（优先级 P0）

**新建文件**：`tools/advisory/flight_impact_advisor.py`

```python
class FlightImpactAdvisor:
    """
    航班影响智能分析
    """

    def analyze_priority_flights(self, affected_flights: list) -> dict:
        """
        分析航班优先级

        Returns:
            {
                "critical_flights": [
                    {
                        "flight_no": "CA1234",
                        "reason": "国际航班，后续联程旅客120人",
                        "suggested_action": "优先恢复机位501"
                    }
                ],
                "cascade_risk": [...],
                "recovery_priority": ["501机位", "A1滑行道", "09跑道"]
            }
        """

    def estimate_recovery_scenarios(self, impact_zone: dict) -> list:
        """
        生成恢复方案对比
        """
```

**具体任务**：

| 任务 ID | 任务 | 说明 |
|--------|-----|------|
| F2.1 | 修复硬编码时间 | 使用 `datetime.now()` 替代 |
| F2.2 | 实现航班优先级排序 | 国际>国内>货运，联程>非联程 |
| F2.3 | 实现级联延误模型 | 追踪同一飞机的后续航班 |
| F2.4 | 生成恢复方案对比 | 多方案评估，推荐最优 |

#### 阶段 3：航迹数据集成（优先级 P1）

**新建文件**：`tools/advisory/taxiway_route_advisor.py`

```python
class TaxiwayRouteAdvisor:
    """
    基于历史航迹的滑行路线建议
    """

    def suggest_alternative_routes(self, blocked_position: str, destination: str) -> dict:
        """
        建议绕避路线

        Returns:
            {
                "blocked_segment": "A1滑行道",
                "alternatives": [
                    {
                        "route": "A2 → B → C1",
                        "extra_time": "+3分钟",
                        "historical_usage": "87%航班使用过此路线",
                        "conflicts": []
                    }
                ],
                "recommended": "A2 → B → C1"
            }
        """

    def identify_congestion_risk(self, impact_zone: dict, time_window: int) -> list:
        """
        识别拥堵风险点
        """
```

**具体任务**：

| 任务 ID | 任务 | 说明 |
|--------|-----|------|
| T3.1 | 预处理航迹数据 | 将 560MB 原始数据处理为滑行模式统计 |
| T3.2 | 构建路线图 | 基于历史数据构建常用滑行路线 |
| T3.3 | 实现绕行建议 | 根据封闭区域推荐替代路线 |
| T3.4 | 集成到建议系统 | 在报告中展示绕行方案 |

#### 阶段 4：综合建议引擎（优先级 P1）

**新建文件**：`tools/advisory/comprehensive_advisor.py`

```python
class ComprehensiveAdvisor:
    """
    综合建议引擎 - 整合拓扑+气象+航班+航迹
    """

    def generate_advice(self, state: AgentState) -> dict:
        """
        生成综合建议报告

        Returns:
            {
                "summary": "501机位燃油泄漏，建议立即执行以下措施",

                "immediate_actions": [
                    "1. 关闭发动机，断开APU电源",
                    "2. 从东北方向（下风向）开始铺设吸油毡"
                ],

                "spatial_advice": {
                    "impact_zone": "影响A1、A2滑行道及09跑道入口",
                    "alternative_routes": "建议使用A3→B→C1绕行",
                    "closure_estimate": "预计关闭45分钟"
                },

                "weather_advice": {
                    "current": "气温18°C，东北风5m/s，能见度8km",
                    "impact": "气象条件适宜清污作业",
                    "window": "未来2小时无降雨预报"
                },

                "flight_advice": {
                    "affected_count": 5,
                    "priority_flight": "CA1234（国际联程，优先恢复）",
                    "cascade_risk": "如延迟超过60分钟，将影响后续12个航班"
                },

                "resource_advice": {
                    "personnel": "清污2人、消防2人、场务1人",
                    "equipment": ["吸油毡x20", "防爆泵x1", "灭火器x4"],
                    "estimated_cost": "约8000元"
                },

                "recovery_plan": {
                    "phase1": "0-15分钟：安全警戒+初步清理",
                    "phase2": "15-30分钟：深度清污+摩擦系数检测",
                    "phase3": "30-45分钟：恢复验收+解除封闭"
                }
            }
        """
```

---

## 实施路线图

### 时间规划

```
┌─────────────────────────────────────────────────────────────────────┐
│ 第 1 阶段 (Week 1-2)：核心功能                                       │
├─────────────────────────────────────────────────────────────────────┤
│ ✅ P0 任务：                                                         │
│   1. 工单数据模型定义 (work_order.py)                                │
│   2. 场景检查项加载 (从 checklist.yaml)                              │
│   3. 气象建议引擎 (weather_impact_advisor.py)                        │
│   4. 修复航班影响预测硬编码                                          │
│                                                                     │
│ 预期成果：                                                          │
│   - 工单从纯文本升级为结构化 JSON                                    │
│   - 气象数据利用率从 5% 提升到 70%                                   │
│   - 航班影响预测可用于实际时间                                       │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 第 2 阶段 (Week 3-4)：智能建议                                       │
├─────────────────────────────────────────────────────────────────────┤
│ ✅ P1 任务：                                                         │
│   1. 作业指导生成器 (generate_work_instructions.py)                  │
│   2. 航班优先级分析 (flight_impact_advisor.py)                       │
│   3. 航迹数据预处理和集成                                            │
│   4. 绕行路线建议 (taxiway_route_advisor.py)                         │
│                                                                     │
│ 预期成果：                                                          │
│   - 自动生成场景感知的作业步骤                                       │
│   - 航班影响分析包含优先级和级联风险                                 │
│   - 滑行路线绕行建议可用                                             │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 第 3 阶段 (Week 5-6)：综合输出                                       │
├─────────────────────────────────────────────────────────────────────┤
│ ✅ P2 任务：                                                         │
│   1. 综合建议引擎 (comprehensive_advisor.py)                         │
│   2. PDF/Excel 工单导出                                              │
│   3. 恢复方案对比评估                                                │
│   4. 资源和成本估算                                                  │
│                                                                     │
│ 预期成果：                                                          │
│   - 一站式综合建议报告                                               │
│   - 多格式工单输出                                                   │
│   - 完整的决策支持系统                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 里程碑

| 里程碑 | 时间点 | 交付物 |
|-------|-------|-------|
| M1 | Week 2 | 结构化工单 JSON 输出 + 气象建议集成 |
| M2 | Week 4 | 智能航班分析 + 绕行路线建议 |
| M3 | Week 6 | 综合建议引擎 + 多格式导出 |

---

## 推荐首先实施的任务

### 按投入产出比排序

| 优先级 | 任务 | 预期价值 | 工作量 | 说明 |
|-------|------|---------|-------|------|
| **1** | 气象建议引擎 | ⭐⭐⭐ | 小 (2-3天) | 数据已有，立即可用 |
| **2** | 修复航班影响硬编码 | ⭐⭐⭐ | 极小 (1天) | 解决关键 Bug |
| **3** | 工单数据模型 | ⭐⭐ | 中 (3-4天) | 结构化基础 |
| **4** | 场景检查项加载 | ⭐⭐ | 中 (3-4天) | 动态化关键步骤 |
| **5** | 航班优先级分析 | ⭐⭐ | 中 (4-5天) | 高价值建议 |

### 快速胜利（Quick Wins）

以下任务可在 1-2 天内完成，立即产生价值：

1. **修复硬编码时间** - `tools/spatial/predict_flight_impact.py:102`
   ```python
   # 当前：
   current_time = datetime.fromisoformat("2025-10-21 11:00:00")
   # 修改为：
   current_time = datetime.now()
   ```

2. **添加气象自动触发** - 在 `reasoning.py` 中当位置确定后自动查询气象

3. **读取场景检查项** - 在 `output_generator.py` 中加载 `checklist.yaml`

---

## 新建文件清单

### 需要创建的文件

| 文件路径 | 用途 | 优先级 |
|---------|------|-------|
| `agent/models/work_order.py` | 工单数据模型 | P0 |
| `tools/advisory/weather_impact_advisor.py` | 气象建议引擎 | P0 |
| `tools/advisory/flight_impact_advisor.py` | 航班影响分析 | P0 |
| `tools/advisory/taxiway_route_advisor.py` | 滑行路线建议 | P1 |
| `tools/advisory/comprehensive_advisor.py` | 综合建议引擎 | P1 |
| `tools/action/generate_work_instructions.py` | 作业指导生成 | P1 |
| `tools/action/assign_responsibilities.py` | 责任分配引擎 | P1 |
| `scenarios/oil_spill/work_order_template.yaml` | 油液工单模板 | P1 |
| `scenarios/bird_strike/work_order_template.yaml` | 鸟击工单模板 | P1 |

### 需要修改的文件

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|-------|
| `tools/spatial/predict_flight_impact.py` | 修复硬编码时间 | P0 |
| `agent/nodes/output_generator.py` | 结构化输出 + 加载检查项 | P0 |
| `agent/nodes/reasoning.py` | 气象自动触发 | P0 |
| `tools/registry.py` | 注册新工具 | P1 |

---

## 预期效果

### 完成后的能力对比

| 能力 | 当前 | 目标 |
|-----|------|------|
| 工单输出格式 | Markdown 纯文本 | JSON + PDF + Excel |
| 检查项生成 | 静态 9 项 | 动态 20+ 项（场景感知） |
| 气象数据利用 | 5% | 80% |
| 航班影响分析 | 简单延误估算 | 优先级+级联风险+恢复方案 |
| 航迹数据利用 | 0% | 60% |
| 综合建议 | 无 | 一站式决策支持 |

### 对管制员的价值

1. **检查工单**：结构化、可追踪、可与其他系统对接
2. **作业指导**：自动生成场景感知的作业步骤，减少人工判断
3. **辅助建议**：
   - 气象：何时作业最优、需要哪些防护
   - 航班：哪些航班优先恢复、延误会传导到哪些后续航班
   - 路线：如何绕行、哪条路线最优
4. **恢复估算**：多方案对比，支持决策

---

## 附录

### A. 相关文件位置

- 报告生成器：`agent/nodes/output_generator.py`
- 航班影响预测：`tools/spatial/predict_flight_impact.py`
- 气象工具：`tools/information/get_weather.py`
- 拓扑加载器：`tools/spatial/topology_loader.py`
- 场景检查项：`scenarios/*/checklist.yaml`
- 航迹解析器：`scripts/data_processing/parse_trajectory.py`

### B. 数据文件位置

- 拓扑数据：`data/spatial/airport_topology.json`
- 气象数据：`data/processed/awos_weather_*.csv`
- 航班计划：`data/raw/航班计划/Log_*.txt`
- 航迹数据：`data/raw/航迹数据/MCR_*.`

---

*文档版本: v1.0*
*最后更新: 2026-01-16*
