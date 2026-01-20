# 机场机坪应急响应智能 Agent 系统

## 项目概述

本系统是一个融合 **ReAct Agent** 与 **FSM 状态机验证** 的智能应急响应系统，专门用于处理机场机坪漏油、鸟击等特情事件。

### 对话模式 🎯

**Agent 角色**：机坪管制员（Apron Controller）
**用户角色**：航空器机长（Captain/PIC）

系统采用 **主动询问模式**，机坪管制Agent向机长收集信息。以下是完整的对话示例：

#### 完整对话示例

```
机坪管制: 天府机坪，请讲。

机长: 天府机坪，川航3349报告紧急情况，右侧发动机有滑油泄漏，可见持续滴漏，泄漏面积不明，请求支援。

机坪管制: 川航3349，具体位置（停机位号/滑行道/跑道）？发动机当前状态？运转中还是已关闭？

机长: 天府机坪 我在滑行道10 发动机已关机

机坪管制: 川航3349，处置流程已完成。你还有什么需要补充的吗？

机长: 天府机坪 无补充信息 完毕
```

#### 鸟击场景简要示例

```
机坪管制: 天府机坪，请讲。

机长: 天府机坪，南航1234报告疑似鸟击，起飞滑跑时左发疑似受损，当前状态异常，请求检查。

机坪管制: 南航1234，鸟击发生在什么阶段？是否有明确迹象（残留/告警/异响/仅怀疑/无异常）？
```

#### 鸟击场景完整对话示例

```
机坪管制: 天府机坪，请讲。

机长: 天府机坪，南航1234报告疑似鸟击，起飞滑跑时左发疑似受损，当前状态异常，请求检查。

机坪管制: 南航1234，确认鸟击发生位置（跑道/滑行道/机位）？

机长: 天府机坪，跑道27L。

机坪管制: 南航1234，鸟击发生在什么阶段？

机长: 起飞滑跑阶段。

机坪管制: 南航1234，是否有明确迹象（残留/告警/异响/仅怀疑/无异常）？

机长: 有异响和振动。

机坪管制: 南航1234，鸟类规模/大小如何？（鸟群/大型鸟/中小型单只/不明）

机长: 鸟群，具体数量不清。

机坪管制: 南航1234，运行影响如何？（返航或中断起飞/占用跑道或滑行道/请求机务检查/不影响运行）

机长: 中断起飞，请求机务检查。

机坪管制: 南航1234，处置流程已完成。你还有什么需要补充的吗？

机长: 天府机坪，无补充信息，完毕。
```

#### 鸟击风险评估示例（BSRC）

```
输入：
phase=TAKEOFF_ROLL
affected_part=左发
event_type=疑似鸟击
current_status=异常
evidence=ABNORMAL_NOISE_VIBRATION
bird_info=FLOCK
ops_impact=RTO_OR_RTB

输出：
risk_level=R4, score=86.5
guardrails.requires_human_approval=true
```

#### 交互流程解析

1. **初始呼叫**
   - 机坪管制主动呼叫，等待机长报告
   - 标准化开场白建立专业沟通氛围

2. **紧急情况报告**
   - 机长报告：航班号、位置、泄漏类型、持续状态
   - Agent 自动提取：航班号、液体类型（滑油）、持续滴漏
   - 触发自动查询：航班计划信息、位置拓扑分析

3. **信息收集（智能引导）**
   - Agent 主动询问关键信息：位置详情、发动机状态
   - 符合实际场景：机坪管制通常需要精确位置和设备状态
   - 逐步收集：fluid_type → position → engine_status → continuous

4. **自动分析与响应**
   - 位置确认：滑行道10 → 拓扑分析 → 影响范围计算
   - 发动机状态：已关机 → 风险等级调整
   - 自动触发：风险评估、空间分析、部门通知

5. **流程完成确认**
   - 处置完成后询问补充信息
   - 标准化结束语

**特点**：
- ✅ 需要符合空中交通管制对话规则
- ✅ 主动引导信息收集流程
- ✅ 符合实际机场运行场景
- ✅ 自动触发分析（航班查询、空间推理、风险评估）
- ✅ 实时反馈分析结果给管制员
- ✅ 漏油场景自动生成综合评估报告（outputs/advice，Markdown+JSON）

#### 运行方式

```bash
# 方式一：简单模拟测试（无需API密钥）
python test_dialogue_example.py --mock

# 方式二：完整自动化测试（推荐）
python test_automated_dialogue.py

# 方式三：交互式终端（需要 LLM API 密钥）
python apps/run_agent.py

# 方式四：真实LLM测试
python test_dialogue_example.py --llm
```

测试说明：
- **简单模拟测试**: 展示对话示例和系统处理结果
- **完整自动化测试**: 详细展示7步处理流程（信息收集→风险评估→空间分析→部门通知→报告生成）
- **交互式终端**: 真实LLM驱动的多轮对话
- **真实LLM测试**: 结合模拟和真实LLM的混合模式

模拟测试会展示完整的对话流程和系统处理结果，包括：
- 信息自动提取（航班号、液体类型、位置、发动机状态）
- 风险评估分析（MEDIUM级风险，45/100分）
- 空间影响分析（滑行道10及周边区域）
- 报告生成（11个标准章节）

详见：[DIALOGUE_ROLE_CHANGE.md](./DIALOGUE_ROLE_CHANGE.md)

### 核心设计理念

```
┌─────────────────────────────────────────────────────────────────┐
│                    融合架构：ReAct 主导 + FSM 验证               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ReAct Agent (主导层)                        │    │
│  │   - LLM 决定推理路径和工具调用顺序                        │    │
│  │   - 灵活应对复杂场景和意外情况                            │    │
│  │   - 受 Checklist 和约束系统约束                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              FSM 验证层 (非驱动层)                        │    │
│  │   - 验证 Agent 是否完成必要步骤                          │    │
│  │   - 确保状态转换符合规范流程                              │    │
│  │   - 检查强制动作是否执行                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              确定性计算层 (工具)                          │    │
│  │   - 风险评估：规则引擎（确定性）                          │    │
│  │   - 空间推理：Graph 算法（确定性）                        │    │
│  │   - LLM 不直接计算，而是调用工具                         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 融合优势

| 来源 | 特性 |
|------|------|
| ReAct Agent | 灵活推理、即时响应、处理意外 |
| FSM 验证 | 可审计、流程合规、状态追踪 |
| 规则引擎 | 确定性风险评估 |
| Graph 算法 | 确定性空间推理 |

## 鸟击场景改进要点

- 新增鸟击风险评估工具 `assess_bird_strike_risk`，基于 `BSRC.json` 规则集输出 R1-R4 风险等级与管控建议。
- 鸟击场景补充字段：`phase`、`evidence`、`bird_info`、`ops_impact`，用于提升风险评估准确度。
- 新增场景字段契约表：`docs/SCENARIO_FIELD_CONTRACTS.md`，对齐工具输出与 FSM/约束使用字段。

## 项目成熟度评估

### 整体评估：45% - Early Beta 阶段

本系统目前处于 **Early Beta** 阶段，适合用于 **POC/演示场景**，但**尚未达到生产就绪**标准。

| 维度 | 得分 | 状态 | 关键问题 |
|------|------|------|----------|
| **架构设计** | ⭐⭐⭐⭐ (4/5) | 优秀 | ReAct+FSM混合设计清晰，关注点分离良好 |
| **测试** | 45% | 开发中 | 无CI/CD、覆盖率报告缺失、根目录测试脚本混乱 |
| **配置管理** | 65% | 尚可 | 无密钥管理、无环境分离(dev/staging/prod)、路径硬编码 |
| **代码质量** | 55% | 混合 | 错误处理不一致、存在超长函数(200-778行)、遗留代码路径 |
| **可观测性** | 28% | ⚠️ 最小化 | **仅11处日志语句**、无指标、无结构化日志、无告警 |
| **部署** | 35% | 基础 | 无Docker、**仅内存存储**(崩溃丢失数据)、无进程管理 |

### 核心优势 ✨

1. **优秀的架构设计**
   - 清晰的 ReAct+FSM 混合架构
   - LLM 负责灵活推理，FSM 负责流程验证，工具负责确定性计算
   - 完美适合安全关键应用

2. **场景驱动配置**
   - YAML 配置实现多场景支持，无需改代码
   - Manifest 自动注册机制，易于扩展

3. **智能自动增强**
   - 并行获取航班信息、拓扑分析、影响区域
   - ThreadPoolExecutor 并行执行减少延迟

4. **确定性计算层**
   - 12条优先级规则的风险评估（无LLM随机性）
   - 基于图算法(BFS)的空间影响分析

### 关键差距 ⚠️

| 问题 | 影响 | 严重性 |
|------|------|--------|
| 仅内存会话存储 | 服务重启或崩溃导致所有会话数据丢失 | 🔴 关键 |
| 无Docker容器化 | 部署困难，环境不一致 | 🔴 关键 |
| 无持久化数据库 | 报告和审计追踪无法长期保存 | 🔴 关键 |
| 最小化日志(11处) | 生产问题无法调试和追踪 | 🔴 关键 |
| 无CI/CD管道 | 依赖手动测试和部署 | 🟠 高 |
| 无密钥管理 | API密钥暴露在版本控制中 | 🟠 高 |
| 无认证层 | API端点完全开放访问 | 🟠 高 |
| 超长函数 | output_generator.py 778行字符串拼接 | 🟡 中 |

### 适用场景

✅ **适合**：
- 概念验证(POC)和技术演示
- 研发环境测试
- 功能原型验证
- 架构设计评审

❌ **不适合**（当前状态）：
- 生产环境部署
- 7×24小时运行服务
- 关键业务场景
- 需要审计追踪的场景

详见：[生产就绪度评估](./docs/PRODUCTION_READINESS.md)

## 目录结构

```
airport-emergency-agent/
├── config/                    # 配置文件
│   ├── settings.py           # 全局配置
│   └── llm_config.py         # LLM 配置
├── scenarios/                 # 场景配置
│   ├── base.py               # 场景基类与注册中心
│   ├── SCENARIO_GUIDE.md     # 场景开发指南
│   ├── oil_spill/            # 漏油场景 (✅ 已实现)
│   │   ├── config.yaml       # 场景配置
│   │   ├── checklist.yaml    # Checklist 定义
│   │   ├── fsm_states.yaml   # FSM 状态定义
│   │   └── prompt.yaml       # ✅ 场景专属 System Prompt
│   └── bird_strike/          # 鸟击场景 (✅ 示例完成)
│       └── prompt.yaml       # ✅ 场景专属 System Prompt
├── agent/                     # Agent 核心
│   ├── state.py              # 状态定义
│   ├── graph.py              # LangGraph 图定义
│   ├── nodes/                # 节点实现
│   │   ├── input_parser.py   # ✅ 输入解析
│   │   ├── reasoning.py      # ✅ ReAct 推理
│   │   ├── tool_executor.py  # ✅ 工具执行
│   │   ├── fsm_validator.py  # ✅ FSM 验证
│   │   └── output_generator.py # ✅ 报告生成
│   └── prompts/              # Prompt 模板
├── tools/                     # 工具实现
│   ├── base.py               # 工具基类
│   ├── registry.py           # 工具注册中心
│   ├── information/          # 信息收集类
│   │   ├── ask_for_detail.py     # ✅ 追问详情
│   │   └── get_aircraft_info.py  # ✅ 获取飞机信息
│   ├── spatial/              # 空间推理类
│   │   ├── get_stand_location.py # ✅ 机位查询
│   │   └── calculate_impact_zone.py # ✅ 影响区域计算
│   ├── knowledge/            # 知识检索类
│   │   └── search_regulations.py # ✅ 规章检索
│   ├── assessment/           # 评估类
│   │   └── assess_risk.py    # ✅ 风险评估
│   └── action/               # 行动类
│       ├── notify_department.py  # ✅ 通知部门
│       └── generate_report.py    # ✅ 生成报告
├── fsm/                       # FSM 验证层
│   ├── engine.py             # FSM 引擎
│   ├── validator.py          # 状态验证器
│   └── states.py             # 状态定义
├── constraints/               # 约束系统
│   ├── loader.py             # ✅ 约束加载器
│   └── checker.py            # ✅ 约束检查器
├── spatial/                   # 空间推理 (✅ 已实现)
│   └── data/                 # 机场拓扑数据
│       └── airport_topology.json  # ✅ 拓扑数据
├── api/                       # API 接口
│   └── main.py               # FastAPI 入口
├── tests/                     # 测试
│   └── test_integration.py   # ✅ 集成测试
├── run_demo.py               # ✅ Demo 脚本（无需 LLM）
├── run_interactive.py        # ✅ 交互模式（需 LLM）
└── pyproject.toml            # ✅ Poetry 配置
```

> **状态标记**: ✅ 已实现 | ⚠️ 部分实现 | ❌ 缺失

## 缺失组件及优先级评估

### 高优先级 (影响核心功能) ✅ 已完成

| 组件 | 状态 | 说明 |
|------|------|------|
| `constraints/loader.py` | ✅ 已完成 | 从 YAML 配置加载约束定义 |
| `constraints/checker.py` | ✅ 已完成 | Checklist 约束检查与强制动作验证 |

### 中优先级 (影响系统完整性) ✅ 已完成

| 组件 | 状态 | 影响 | 预估工作量 |
|------|------|------|-----------|
| `tools/assessment/assess_oil_spill_risk.py` | ✅ 已完成 | 漏油风险规则与评分映射已实现 | - |
| `tools/spatial/topology_loader.py` | ✅ 已完成 | 机场拓扑加载与节点查询已实现 | - |
| `tools/spatial/calculate_impact_zone.py` | ✅ 已完成 | BFS 扩散与影响范围计算已实现 | - |
| `tools/spatial/predict_flight_impact.py` | ✅ 已完成 | 历史航班 + 拓扑影响预测已实现 | - |

### 低优先级 (扩展功能)

| 组件 | 状态 | 说明 | 预估工作量 |
|------|------|------|-----------|
| `knowledge/retriever.py` | ⚠️ 使用中 | 当前 `search_regulations.py` 已实现基本功能 | - |
| `scenarios/bird_strike/` | ✅ 已完成 | 完整鸟击场景 + BSRC 风险评估 | - |
| `scenarios/tire_burst/` | ❌ 缺失 | 轮胎爆破场景 | 1-2 周 |
| `scenarios/runway_incursion/` | ❌ 缺失 | 跑道入侵场景 | 2-3 周 |

### 实现建议

**阶段一 (核心修复)** - ✅ 已完成
1. 实现 `constraints/` 完整约束系统 - 确保流程合规 ✅

**阶段二 (能力增强)** - ✅ 已完成：
1. 完善 `tools/assessment/assess_oil_spill_risk.py` - 风险评估规则与评分映射 ✅
2. 实现 `tools/spatial/topology_loader.py` - 机场拓扑建模 ✅
3. 实现 `tools/spatial/calculate_impact_zone.py`/`tools/spatial/predict_flight_impact.py` - 影响范围与航班预测 ✅

**阶段三 (场景扩展)**：
1. 添加更多应急场景支持

## 快速开始

### 环境要求

- Python 3.10+
- LangGraph
- FastAPI
- Shapely (空间推理)

### 安装

```bash
# 使用 Poetry 安装（推荐）
pip install poetry
poetry install

# 或使用 pip
pip install -e ".[dev,llm]"
```

### 运行

```bash
# 启动 API 服务
python -m apps.api.main

# 运行 Demo 脚本（无需 LLM）
python run_demo.py

# 交互模式（需配置 LLM_API_KEY）
python run_interactive.py

# 运行测试
python -m pytest tests/
```

### 输出目录

- `outputs/reports/`: 最终处置报告（按场景分类）
- `outputs/advice/`: 漏油综合评估报告（Markdown + JSON）

### 环境配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置（支持 zhipu 和 openai 提供商）
# LLM_PROVIDER=zhipu
# LLM_MODEL=glm-4
# LLM_API_KEY=your_api_key
```

## 核心流程

```
用户输入 → 输入解析 → ReAct 推理循环 → FSM 验证 → 输出报告
                          ↓
                    ┌─────────────┐
                    │  工具调用    │
                    ├─────────────┤
                    │ - 追问信息   │
                    │ - 风险评估   │
                    │ - 空间分析   │
                    │ - 通知部门   │
                    │ - 生成报告   │
                    └─────────────┘
```

## 详细数据流分析

### 完整数据流

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 用户输入处理 (input_parser_node)                          │
├─────────────────────────────────────────────────────────────┤
│ 用户输入文本                                                  │
│   ↓                                                          │
│ normalize_radiotelephony_text() ─→ 处理ATC无线电术语          │
│   ↓                                                          │
│ identify_scenario() ─→ 场景识别（油液泄漏/鸟击等）             │
│   ↓                                                          │
│ 实体提取（受 ENABLE_SEMANTIC_UNDERSTANDING 影响）              │
│   ├─ 开启：LLM对话理解 + 规则提取（extract_entities）           │
│   └─ 关闭：extract_entities_hybrid（正则 + LLM）               │
│   ↓                                                          │
│ apply_auto_enrichment() ──→ 🔄 并行自动增强                   │
│   ├─ Phase 1（并行执行 ThreadPoolExecutor）：                 │
│   │  ├─ get_aircraft_info(flight_no) ─→ 查询航班信息           │
│   │  ├─ flight_plan_lookup(flight_no) ─→ 查询航班计划          │
│   │  └─ get_stand_location(position) ─→ 查询机位位置           │
│   ├─ Phase 2（依赖Phase 1结果）：                             │
│   │  ├─ calculate_impact_zone() ─→ BFS图扩散算法              │
│   │  └─ analyze_position_impact() ─→ 位置影响分析             │
│   └─ 超时处理：10秒超时，优雅降级                              │
│   ↓                                                          │
│ update_checklist() ─→ 标记已收集字段                          │
│   ↓                                                          │
│ 输出：更新后的 AgentState                                     │
│   ├─ incident：实体+增强数据                                  │
│   ├─ checklist：字段完成状态                                  │
│   ├─ spatial_analysis：拓扑分析结果                           │
│   ├─ flight_plan_table：航班计划                             │
│   └─ observations：增强过程记录                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. ReAct 推理循环 (reasoning_node)                           │
├─────────────────────────────────────────────────────────────┤
│ 构建上下文摘要：                                              │
│   ├─ 航班信息（航空公司、机位、跑道、航班类型）                 │
│   ├─ 事件信息（位置、液体、发动机状态、持续性）                 │
│   ├─ 拓扑分析（影响区域、受影响滑行道/跑道）                    │
│   ├─ 航班影响预测（受影响航班列表）                             │
│   └─ Checklist状态（已收集/缺失字段）                          │
│   ↓                                                          │
│ 调用 LLM（ReAct格式）：                                        │
│   输入：system_prompt + context_summary + dialogue_history    │
│   输出：{"thought": "...", "action": "...", "action_input": {...}}│
│   ↓                                                          │
│ 解析 LLM 输出：                                                │
│   ├─ 成功：提取 action + action_input                         │
│   ├─ 失败：重试（最多1次）                                     │
│   └─ 兜底：fallback extraction 提取候选工具                   │
│   ↓                                                          │
│ 路由决策（should_continue）：                                  │
│   ├─ final_answer 存在 → output_generator                    │
│   ├─ action 存在 → tool_executor                             │
│   └─ 否则 → end                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3. 工具执行 (tool_executor_node)                             │
├─────────────────────────────────────────────────────────────┤
│ 工具查找：ToolRegistry.get_by_scenario()                      │
│   ↓                                                          │
│ 执行工具：tool.execute(state, inputs)                         │
│   ├─ assess_risk → 规则引擎计算风险等级                        │
│   │  └─ 12条优先级规则：                                       │
│   │     (FUEL + continuous + RUNNING) → HIGH (95分)          │
│   │     (FUEL + RUNNING) → HIGH (90分)                       │
│   │     ...                                                  │
│   │     (OIL) → LOW (25分)                                   │
│   ├─ calculate_impact_zone → BFS图扩散                       │
│   │  └─ 规则：FUEL HIGH=3跳, MEDIUM=2跳                      │
│   ├─ get_weather → 查询最新气象记录                           │
│   │  └─ 位置无数据时回退到就近观测点，并提示                   │
│   ├─ notify_department → 通知相关部门                        │
│   └─ generate_report → 触发报告生成                          │
│   ↓                                                          │
│ 状态更新：合并工具结果到 AgentState                            │
│   ├─ risk_assessment：风险等级、得分、因素                     │
│   ├─ spatial_analysis：影响区域、受影响设施                    │
│   ├─ notifications_sent：通知记录                             │
│   └─ actions_taken：动作历史                                 │
│   ↓                                                          │
│ 路由决策（after_tool_execution）：                             │
│   ├─ 关键工具（assess_risk/calculate_impact_zone/notify） →   │
│   │  fsm_validator（触发验证）                                │
│   └─ 其他工具 → reasoning（继续推理）                          │
└─────────────────────────────────────────────────────────────┘

自动气象查询：
- 当 position 已知时由 reasoning 触发 `get_weather`，使用 `incident.position`。
- 位置无数据会自动回退到就近观测点并提示。
- 同一位置只查询一次，位置变化才会再次查询。

## 实体抽取流程（当前实现）

1. 文本规范化：`normalize_radiotelephony_text()` 将口语数字与跑道方位规范化（如“跑道27左→跑道27L”）。
2. 航空读法规范化：`RadiotelephonyNormalizer`（LLM + 规则检索）生成 `normalized_text` 与候选 `entities`。
3. 场景识别：`identify_scenario()` 判定油液/鸟击等场景。
4. 实体抽取路径（受 `ENABLE_SEMANTIC_UNDERSTANDING` 影响）：
   - 开启：`understand_conversation()`（对话语义理解）→ `extract_entities()`（规则补充）→ 合并。
   - 关闭：`extract_entities_hybrid()`（正则 + LLM）→ 用 `RadiotelephonyNormalizer` 的 `entities` 覆盖。
5. 自动补全：`apply_auto_enrichment()` 并行补航班信息/航班计划/位置拓扑；气象查询改由 `reasoning -> tool_executor(get_weather)` 触发。

## 实体抽取方案优缺点

优点：
- 双层规范化提升航班号/位置解析稳定性（无线电口语→标准格式）。
- 语义理解可开关，复杂语句有更高覆盖率，关闭时更可控更快。
- 正则兜底保证弱网/LLM失败时仍可提取关键字段。
- 抽取与补全解耦，补全并行执行、可降级。

缺点：
- 开启/关闭语义理解时抽取路径不同，行为差异明显。
- 规则库覆盖有限，机场本地化表达容易漏。
- 规范化依赖 LLM，网络异常会降级影响质量。
- 多源合并存在冲突风险，需要人工确认。

┌─────────────────────────────────────────────────────────────┐
│ 4. FSM 验证 (fsm_validator_node)                             │
├─────────────────────────────────────────────────────────────┤
│ 同步 Agent 状态：sync_with_agent_state()                      │
│   └─ 推断当前 FSM 状态（INIT→P1→P2→...→P8→COMPLETED）         │
│   ↓                                                          │
│ 检查前置条件：check_preconditions()                            │
│   └─ 例如：进入 P2_IMMEDIATE_CONTROL 需要 risk_assessed=true │
│   ↓                                                          │
│ 检查强制动作：check_mandatory_actions()                        │
│   ├─ HIGH风险 + fire_dept_notified=false →                   │
│   │  pending_action: notify_department(消防)                 │
│   ├─ affected_runways 非空 + atc_notified=false →            │
│   │  pending_action: notify_department(塔台)                 │
│   └─ 其他场景特定强制动作                                     │
│   ↓                                                          │
│ 返回：FSMValidationResult                                     │
│   ├─ is_valid：验证是否通过                                   │
│   ├─ errors：错误信息列表                                     │
│   ├─ pending_actions：待执行强制动作                          │
│   └─ inferred_state：推断的FSM状态                            │
│   ↓                                                          │
│ 路由决策（after_fsm_validation）：                             │
│   ├─ 有错误/待执行动作 → reasoning（Agent处理）                │
│   ├─ FSM状态=COMPLETED → output_generator                    │
│   ├─ FSM状态=P8_CLOSE + 有待执行 → reasoning                  │
│   └─ 否则 → reasoning（继续）                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 5. 报告生成 (output_generator_node)                          │
├─────────────────────────────────────────────────────────────┤
│ 收集数据：                                                    │
│   ├─ incident：最终事件状态                                   │
│   ├─ risk_assessment：风险等级+因素                           │
│   ├─ spatial_analysis：受影响区域                             │
│   ├─ actions_taken：处置历史                                  │
│   ├─ notifications_sent：通知记录                             │
│   ├─ flight_impact_prediction：航班影响                       │
│   └─ messages：对话历史                                       │
│   ↓                                                          │
│ 生成报告（⚠️ 当前：778行字符串拼接）：                          │
│   ├─ 标题、事件摘要、风险等级                                  │
│   ├─ 处置过程（动作时间线）                                    │
│   ├─ Checklist 项目（P1/P2字段）                              │
│   ├─ 协同单位（通知记录）                                      │
│   ├─ 运行影响（受影响航班、关闭时间）                           │
│   └─ 建议措施（安全措施、后续跟进）                             │
│   ↓                                                          │
│ 调用 LLM 生成摘要（可选）                                       │
│   ↓                                                          │
│ 输出：final_report (dict) + final_answer (str)               │
│   ↓                                                          │
│ 等待用户确认：awaiting_user = True                            │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计模式

1. **混合实体提取**
   - 正则表达式：快速路径，处理结构化数据（航班号、位置）
   - LLM语义提取：灵活路径，处理自然语言模糊表述
   - 优先级：LLM结果覆盖正则结果

2. **并行自动增强**
   - Phase 1：独立查询并行执行（ThreadPoolExecutor）
   - Phase 2：依赖计算串行执行
   - 超时保护：10秒超时，优雅降级

3. **确定性计算层**
   - 风险评估：12条优先级规则，确定性评分
   - 空间分析：BFS图算法，确定性扩散
   - 不依赖LLM进行关键计算

4. **FSM验证非驱动**
   - FSM不控制流程，仅验证Agent行为
   - 发现问题时返回错误，由Agent自行修正
   - 保留LLM灵活性，同时确保流程合规

## 支持的场景

### 场景 Prompt 系统

每个场景拥有独立的 `prompt.yaml` 配置文件，定义：
- `system_prompt`: 场景专属 System Prompt
- `field_order`: 信息收集顺序（强制按序询问）
- `field_names`: 字段中文名称映射
- `ask_prompts`: 各字段的追问提示

```
scenarios/
├── oil_spill/prompt.yaml      # 漏油场景 Prompt
│   field_order:
│     - flight_no     # 1. 航班号
│     - position      # 2. 事发位置
│     - fluid_type    # 3. 油液类型
│     - engine_status # 4. 发动机状态
│     - continuous    # 5. 是否持续滴漏
│     - leak_size     # 6. 泄漏面积
│
└── bird_strike/prompt.yaml    # 鸟击场景 Prompt（示例）
    field_order:
      - flight_no     # 1. 航班号
      - position      # 2. 事发位置
      - strike_area   # 3. 撞击部位
      - engine_status # 4. 发动机状态
      - flight_phase  # 5. 飞行阶段
```

### 场景列表

| 场景 | 状态 | 说明 |
|------|------|------|
| oil_spill | ✅ 已实现 | 油液泄漏处理 |
| bird_strike | ✅ 示例 | 鸟击事件（可扩展） |
| tire_burst | ⏳ 规划中 | 轮胎爆破场景 |
| runway_incursion | ⏳ 规划中 | 跑道入侵场景 |

### 添加新场景

1. 创建 `scenarios/<场景名>/` 目录
2. 添加 `prompt.yaml`（必需）
3. 可选：添加 `config.yaml`, `checklist.yaml`, `fsm_states.yaml`
4. 在 `scenarios/base.py` 中注册新场景类

详细指南见 [SCENARIO_GUIDE.md](scenarios/SCENARIO_GUIDE.md)

## 工程化现状

### 测试基础设施 (45%)

✅ **已有**：
- 18个测试文件，良好的pytest结构
- 参数化单元测试 (`@pytest.mark.parametrize`)
- 集成测试覆盖关键路径（风险评估、FSM转换、拓扑分析）

❌ **缺失**：
- 无覆盖率报告配置
- 无CI/CD管道（GitHub Actions、GitLab CI等）
- 根目录测试脚本混乱（`test_*.py`, `quick_test_agent.py`需清理）
- 无性能测试或负载测试

### 可观测性 (28%)

✅ **已有**：
- 请求ID追踪（通过中间件）
- 全局异常处理
- 可选LangSmith追踪

❌ **缺失**（⚠️ 严重不足）：
- **仅11处日志语句**（整个系统）
- 无结构化日志（JSON格式）
- 无指标收集（Prometheus、StatsD）
- 无健康检查端点
- 无分布式追踪
- 无性能监控

### 部署就绪 (35%)

✅ **已有**：
- setuptools打包和入口点
- FastAPI + uvicorn
- 分离的可选依赖（dev、llm、vector）

❌ **缺失**（🔴 阻塞生产）：
- **无Docker/Kubernetes支持**
- **仅内存会话存储（MemorySessionStore）**
  - 服务重启丢失所有会话
  - 无跨实例会话共享
- 无数据库配置
- 无认证/授权
- CORS默认允许 "*"（安全风险）
- DEBUG模式暴露系统信息

## 生产部署考虑

### 必备功能（阻塞生产）

1. **持久化存储**
   - 替换 MemorySessionStore 为 PostgreSQL/Redis
   - 会话数据库表
   - 报告存储表
   - 迁移策略：`create_session_store()` 工厂模式

2. **容器化**
   - Dockerfile（多阶段构建）
   - docker-compose.yml（本地开发）
   - Kubernetes配置（生产环境）

3. **日志系统**
   - 结构化JSON日志
   - 日志轮转和保留
   - 关键路径日志：
     - `input_parser`：实体提取结果
     - `reasoning`：ReAct决策
     - `tool_executor`：工具执行+结果
     - `fsm_validator`：验证错误
     - `output_generator`：报告生成

4. **监控和健康检查**
   - `/health` 端点（liveness + readiness）
   - Prometheus指标：
     - 请求计数（按端点）
     - 响应时间（p50、p95、p99）
     - 活动会话数
     - 工具执行计数

5. **安全**
   - API密钥认证
   - 密钥管理（AWS Secrets Manager、Vault）
   - 速率限制
   - CORS适当配置

### 应有功能（高优先级）

- 配置分离（dev/staging/prod）
- CI/CD管道
- 错误跟踪集成（Sentry）
- 测试覆盖率报告
- API文档（OpenAPI/Swagger）

### 可选功能（增强）

- 缓存层（Redis）
- 消息队列（Celery/RabbitMQ）
- 分布式追踪（Jaeger/Datadog）
- 自定义Prometheus指标

详见：[部署指南](./docs/DEPLOYMENT_GUIDE.md)

## 改进路线图

### 阶段 1：生产就绪基础 (1-2周)

**目标**：解决阻塞生产的关键问题

- [ ] PostgreSQL会话存储
- [ ] Docker容器化
- [ ] 结构化日志系统
- [ ] 健康检查和基本指标
- [ ] 数据库报告存储

**预期收益**：
- 服务重启不丢失数据
- 标准化部署流程
- 可调试生产问题

### 阶段 2：安全与认证 (1周)

**目标**：保护API访问

- [ ] 密钥管理集成
- [ ] API密钥认证
- [ ] 速率限制
- [ ] CORS适当配置
- [ ] 安全审计

**预期收益**：
- API访问受控
- 密钥安全存储
- 防止滥用

### 阶段 3：代码重构 (2-3周)

**目标**：提高代码可维护性（参考 `docs/refactoring_plan.md`）

- [ ] Jinja2模板化报告（778行→50行）
- [ ] 分解超长函数（input_parser 495行、build_scenario_prompt 200行）
- [ ] 外部化规则到YAML（风险评估、空间影响）
- [ ] 统一Pydantic模型（替换TypedDict混用）

**预期收益**：
- 代码可读性提升
- 非技术人员可调整规则
- 测试更容易

### 阶段 4：测试与CI/CD (1-2周)

**目标**：自动化测试和部署

- [ ] pytest-cov配置
- [ ] 覆盖率目标（80%+）
- [ ] GitHub Actions工作流
- [ ] 集成测试套件
- [ ] 性能基准测试

**预期收益**：
- 自动化测试
- 部署信心提升
- 快速反馈循环

### 阶段 5：文档改进 (持续)

- [ ] API文档（OpenAPI/Swagger）
- [ ] 工具开发指南
- [ ] 配置模式文档
- [ ] 部署指南
- [ ] 故障排除指南

**预期时间线**：6-8周完整实施

**预期提升**：
- 生产就绪度：45% → 85%+
- 可观测性：28% → 75%+
- 文档质量：6/10 → 9/10

## 已知问题与限制

### 架构限制

| 问题 | 影响 | 解决方案 |
|------|------|----------|
| 仅内存会话存储 | 服务重启丢失所有会话数据 | 阶段1：实现PostgreSQL存储 |
| 报告字符串拼接（778行） | 维护困难，无法自定义模板 | 阶段3：迁移到Jinja2模板 |
| 硬编码风险规则 | 规则变更需要代码部署 | 阶段3：外部化到YAML配置 |
| 全局可变状态 | 非线程安全，并发问题 | 阶段3：依赖注入单例模式 |

### 运维限制

| 问题 | 影响 | 解决方案 |
|------|------|----------|
| 无Docker支持 | 部署困难，环境不一致 | 阶段1：创建Dockerfile |
| 最小化日志（11处） | 无法追踪问题根因 | 阶段1：添加结构化日志 |
| 无健康检查 | 无法监控服务状态 | 阶段1：实现/health端点 |
| 无认证 | API完全开放 | 阶段2：API密钥认证 |
| DEBUG暴露信息 | 安全风险 | 阶段2：安全审计 |

### 功能限制

| 问题 | 影响 | 状态 |
|------|------|------|
| 航班影响预测 | 已支持历史航班 + 拓扑联动预测 | ✅ 已实现 |
| 多场景报告模板 | oil_spill/bird_strike/fod 模板已提供 | ✅ 已实现 |
| 无提示版本控制 | 无法A/B测试或回滚提示 | 计划中（阶段5） |
| 无中间件/钩子系统 | 扩展点有限 | 计划中（阶段5） |

### 测试限制

| 问题 | 影响 | 解决方案 |
|------|------|----------|
| 无CI/CD | 依赖手动测试 | 阶段4：GitHub Actions |
| 无覆盖率报告 | 不知道测试盲区 | 阶段4：pytest-cov |
| 根目录测试混乱 | 维护困难 | 阶段4：清理到tests/ |

## 相关文档

- [架构决策记录](./docs/ARCHITECTURE_DECISIONS.md) - 设计决策和权衡分析
- [生产就绪度评估](./docs/PRODUCTION_READINESS.md) - 完整的工程成熟度评估
- [API文档](./docs/API_DOCUMENTATION.md) - 端点详细说明
- [部署指南](./docs/DEPLOYMENT_GUIDE.md) - Docker、K8s、监控配置
- [工具开发指南](./docs/TOOL_DEVELOPMENT_GUIDE.md) - 创建新工具教程
- [场景开发指南](./scenarios/SCENARIO_GUIDE.md) - 添加新场景说明
- [场景字段契约表](./docs/SCENARIO_FIELD_CONTRACTS.md) - 工具输出与FSM/约束字段对齐

## License

MIT License
