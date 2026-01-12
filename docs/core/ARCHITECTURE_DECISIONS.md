# 架构决策记录 (ADR)

本文档记录 AERO Agent 系统的关键架构决策、设计原理和权衡分析。

---

## ADR-001: 采用 ReAct + FSM 混合架构

**日期**: 2024-01
**状态**: ✅ 已采纳
**决策者**: 核心开发团队

### 背景

机场应急响应系统需要：
1. **灵活性**：处理复杂多变的应急场景
2. **合规性**：确保处置流程符合规范
3. **可审计性**：记录完整的决策过程
4. **确定性**：关键计算（风险评估、空间分析）必须确定可靠

### 决策

采用 **ReAct Agent + FSM 验证** 混合架构：
- **ReAct Agent**: 负责推理和决策（使用 LLM）
- **FSM**: 负责流程验证和合规检查（规则引擎）
- **确定性工具**: 负责关键计算（不使用 LLM）

```
用户输入 → ReAct推理 → 工具执行 → FSM验证 → 继续或修正
             ↑______________|_____________|
```

### 选项对比

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **纯 LLM** | 最灵活 | 不确定、不可审计、无流程保障 | ⭐⭐ |
| **纯规则引擎** | 确定、可审计 | 僵化、无法处理意外 | ⭐⭐⭐ |
| **ReAct + FSM 混合** | 灵活+合规+可审计 | 复杂度较高 | ⭐⭐⭐⭐⭐ |
| **有限状态机驱动** | 流程清晰 | LLM沦为填空工具，失去推理能力 | ⭐⭐⭐ |

### 设计原理

1. **验证非驱动**: FSM不控制流程，仅验证Agent行为
2. **LLM负责灵活推理**: Agent自主决定工具调用顺序
3. **规则负责安全边界**: FSM确保不跳过关键步骤
4. **确定性工具**: 风险评估、空间分析使用算法而非LLM

### 结果

✅ 实现灵活性与合规性的平衡
✅ Agent可处理复杂场景和意外情况
✅ FSM提供可审计的流程保障
⚠️ 增加了系统复杂度，需要维护两套逻辑

---

## ADR-002: 选择 LangGraph 作为 Agent 框架

**日期**: 2024-01
**状态**: ✅ 已采纳

### 背景

需要一个支持：
- 复杂状态管理
- 条件路由
- 多节点协作
- 可视化调试

的 Agent 框架。

### 决策

选择 **LangGraph** 而非 LangChain AgentExecutor 或自建框架。

### 选项对比

| 框架 | 优点 | 缺点 |
|------|------|------|
| **LangGraph** | 图状态机、灵活路由、可视化 | 学习曲线、较新 |
| **LangChain AgentExecutor** | 简单、成熟 | 不够灵活、难以定制流程 |
| **AutoGPT/BabyAGI** | 完全自主 | 不可控、成本高 |
| **自建框架** | 完全控制 | 开发成本高、缺少生态 |

### 设计原理

LangGraph 提供：
1. **StateGraph**: 清晰的状态管理
2. **条件边**: 支持复杂路由（`should_continue()`, `after_tool_execution()`）
3. **检查点**: 可恢复和回溯
4. **可视化**: 图结构易于调试

### 代码示例

```python
workflow = StateGraph(AgentState)

workflow.add_node("input_parser", input_parser_node)
workflow.add_node("reasoning", reasoning_node)
workflow.add_node("tool_executor", tool_executor_node)
workflow.add_node("fsm_validator", fsm_validator_node)

workflow.add_conditional_edges(
    "reasoning",
    should_continue,
    {
        "tool_executor": "tool_executor",
        "output_generator": "output_generator",
        "end": END
    }
)
```

### 结果

✅ 清晰的图结构，易于理解和维护
✅ 灵活的路由支持 ReAct + FSM 融合
✅ TypedDict 状态管理，类型安全
⚠️ 团队需要学习 LangGraph API

---

## ADR-003: 场景驱动配置系统

**日期**: 2024-01
**状态**: ✅ 已采纳

### 背景

系统需要支持多种应急场景（漏油、鸟击、轮胎爆裂等），每种场景有不同的：
- System Prompt
- 信息收集字段
- FSM 状态流程
- 风险评估规则

### 决策

采用 **YAML 配置驱动**的场景系统，而非硬编码场景逻辑。

### 选项对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **YAML 配置** | 易于扩展、非技术人员可编辑 | 需要加载器、验证逻辑 |
| **Python 子类** | 类型安全、IDE支持 | 添加场景需改代码、部署 |
| **数据库配置** | 动态更新 | 复杂、需要管理界面 |

### 设计原理

每个场景包含4个配置文件：

```
scenarios/
└── oil_spill/
    ├── prompt.yaml        # System prompt + 字段顺序
    ├── checklist.yaml     # P1/P2 字段定义
    ├── fsm_states.yaml    # FSM 状态流程
    ├── config.yaml        # 场景元数据
    └── manifest.yaml      # 自动注册

信息
```

**prompt.yaml 示例**:
```yaml
system_prompt: |
  你是机场机坪应急响应专家...

field_order:
  - flight_no
  - position
  - fluid_type
  - engine_status

field_names:
  flight_no: 航班号
  position: 事发位置

ask_prompts:
  flight_no: "请提供涉事飞机的航班号？"
```

### 结果

✅ 添加新场景无需修改代码
✅ 非开发人员可调整提示和流程
✅ 场景配置版本化（Git 管理）
⚠️ 需要维护4个 YAML 文件（维护负担）
⚠️ 无 YAML 模式验证（运行时才发现错误）

---

## ADR-004: 确定性计算层设计

**日期**: 2024-01
**状态**: ✅ 已采纳

### 背景

关键计算（风险评估、空间分析）如果使用 LLM 会有问题：
- **不确定性**: 相同输入可能产生不同输出
- **不可审计**: 无法解释为何得出此结论
- **成本**: 每次计算都调用 LLM API
- **延迟**: LLM 调用慢

### 决策

关键计算使用 **确定性算法**，不使用 LLM：
- 风险评估：规则引擎（12条优先级规则）
- 空间分析：图算法（BFS 扩散）
- 航班查询：数据库查询

### 选项对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **确定性算法** | 可靠、快速、可审计 | 需要定义规则 |
| **LLM 计算** | 灵活 | 不确定、成本高、慢 |
| **混合** | 平衡 | 复杂 |

### 设计原理

**风险评估规则引擎**:
```python
RISK_RULES = [
    {
        "priority": 1,
        "conditions": {
            "fluid_type": "FUEL",
            "continuous": True,
            "engine_status": "RUNNING"
        },
        "result": {"level": "HIGH", "score": 95}
    },
    # ... 共12条规则
]

def assess_risk(incident):
    for rule in sorted(RISK_RULES, key=lambda r: r["priority"]):
        if match_conditions(rule["conditions"], incident):
            return rule["result"]
```

**空间分析图算法**:
```python
def calculate_impact_zone(position, fluid_type, risk_level):
    graph = load_topology()
    start_node = find_nearest_node(graph, position)

    # BFS 扩散
    radius = get_spread_radius(fluid_type, risk_level)
    affected_nodes = bfs_spread(graph, start_node, radius)

    return {
        "isolated_nodes": affected_nodes,
        "affected_taxiways": filter_taxiways(affected_nodes),
        "affected_runways": filter_runways(affected_nodes)
    }
```

### 结果

✅ 计算结果一致可靠
✅ 响应速度快（毫秒级）
✅ 零 LLM API 成本
✅ 完全可审计和可解释
⚠️ 规则需要手动维护
⚠️ 无法处理规则未覆盖的情况

---

## ADR-005: 并行自动增强策略

**日期**: 2024-01
**状态**: ✅ 已采纳

### 背景

每次用户输入后需要查询多个数据源：
- 航班信息
- 航班计划
- 机位位置
- 拓扑分析
- 影响区域

串行执行会导致延迟累加。

### 决策

采用 **并行自动增强**策略，使用 ThreadPoolExecutor 并行执行独立查询。

### 设计原理

**Phase 1**: 独立查询并行执行
```python
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(get_aircraft_info, flight_no): "aircraft",
        executor.submit(flight_plan_lookup, flight_no): "flight_plan",
        executor.submit(get_stand_location, position): "location"
    }

    for future in as_completed(futures, timeout=10):
        result_type = futures[future]
        try:
            results[result_type] = future.result()
        except TimeoutError:
            logger.warning(f"{result_type} query timeout")
```

**Phase 2**: 依赖计算串行执行
```python
# 依赖 Phase 1 的位置数据
if results.get("location"):
    impact_zone = calculate_impact_zone(
        position, fluid_type, risk_level
    )
```

### 结果

✅ 延迟从 5-8秒 降至 2-3秒
✅ 超时保护，优雅降级
✅ 用户体验改善
⚠️ 增加了并发复杂度
⚠️ 需要管理线程池资源

---

## ADR-006: 内存会话存储（临时方案）

**日期**: 2024-01
**状态**: ⚠️ 临时采纳，待替换

### 背景

系统需要会话存储来保持多轮对话状态。

### 决策

当前使用 **MemorySessionStore**（仅内存），作为快速原型的临时方案。

### 权衡

| 方案 | 优点 | 缺点 |
|------|------|------|
| **内存存储** | 简单、快速 | 重启丢失、无法扩展 |
| **PostgreSQL** | 持久化、ACID | 需要配置数据库 |
| **Redis** | 快速、分布式 | 需要 Redis 服务 |

### 当前实现

```python
class MemorySessionStore(SessionStore):
    def __init__(self):
        self._sessions: Dict[str, AgentState] = {}

    def save(self, session_id: str, state: AgentState):
        self._sessions[session_id] = state

    def get(self, session_id: str) -> Optional[AgentState]:
        return self._sessions.get(session_id)
```

### 计划迁移

阶段 1 (立即): 实现 PostgreSQL 会话存储
阶段 2 (后续): 添加 Redis 缓存层

### 结果

⚠️ **生产阻塞**: 服务重启丢失所有会话
✅ 原型开发快速
🔜 必须在生产前替换

---

## ADR-007: 报告生成：字符串拼接 vs 模板引擎

**日期**: 2024-01
**状态**: ⚠️ 待重构

### 背景

需要生成结构化的应急响应报告。

### 当前实现

使用 **778行字符串拼接**：
```python
def generate_output_node(state):
    report = "# 机坪应急响应检查单\n\n"
    report += f"## 1. 事件摘要\n"
    report += f"**发生时间**: {timestamp}\n"
    # ... 778 lines ...
    return report
```

### 问题

- ❌ 代码可读性差
- ❌ 难以维护
- ❌ 无法为不同场景定制模板
- ❌ 无法由非技术人员编辑

### 计划重构

使用 **Jinja2 模板引擎**：
```python
# 目标实现（~50行）
def generate_output_node(state):
    template = env.get_template(f"{scenario_type}/report.j2")
    return template.render(
        incident=state["incident"],
        risk=state["risk_assessment"],
        actions=state["actions_taken"],
        timestamp=datetime.now()
    )
```

```jinja2
{# scenarios/oil_spill/report.j2 #}
# 机坪应急响应检查单

## 1. 事件摘要
**发生时间**: {{ timestamp }}
**航班号**: {{ incident.flight_no }}
**位置**: {{ incident.position }}
**风险等级**: {{ risk.level }}

## 2. 处置过程
{% for action in actions %}
- {{ action.timestamp }} - {{ action.description }}
{% endfor %}
```

### 结果

⚠️ 当前方案不可持续
🔜 重构为模板引擎（阶段3优先级）

---

## 决策原则总结

### 核心原则

1. **灵活性优先**: LLM 处理复杂推理，规则处理确定计算
2. **安全边界**: FSM 确保流程合规，不依赖 LLM 判断关键步骤
3. **可审计性**: 所有决策可追溯，关键计算确定性
4. **渐进式改进**: 先实现核心功能，再优化（如：内存存储→PostgreSQL）
5. **配置驱动**: 场景通过 YAML 定义，减少代码变更

### 权衡考虑

| 维度 | 倾向 | 原因 |
|------|------|------|
| **灵活性 vs 确定性** | 混合 | LLM 负责推理，规则负责计算 |
| **复杂度 vs 功能** | 适中 | 避免过度工程，保持可维护性 |
| **开发速度 vs 生产就绪** | 开发优先 | 快速验证概念，后续加固 |
| **通用性 vs 专用性** | 场景特化 | 每个场景有独特需求 |

---

## 未来决策待定

### 待评估的方案

1. **流式响应**: WebSocket 实时返回 Agent 推理过程
2. **多模态输入**: 支持图片、视频输入（视觉识别泄漏区域）
3. **主动学习**: 从历史案例学习改进提示
4. **分布式部署**: Kubernetes 多实例部署
5. **离线模式**: 支持无网络环境运行（使用本地 LLM）

---

## 参考文档

- [README.md](../README.md) - 项目概述
- [CLAUDE.md](../CLAUDE.md) - 开发指南
- [生产就绪度评估](./PRODUCTION_READINESS.md) - 当前状态
- [重构计划](./refactoring_plan.md) - 计划改进

---

**贡献**: 如有新的架构决策，请按 ADR 格式添加到本文档。
