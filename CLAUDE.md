# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Airport emergency response intelligent agent system that combines **ReAct Agent** with **FSM (Finite State Machine) validation** for handling airport apron incidents like fuel spills and bird strikes. The system uses LLM-driven reasoning while ensuring compliance through deterministic validation layers.

## Development Commands

```bash
# Install dependencies
pip install -e ".[dev,llm]"

# Run tests (all tests are in tests/ directory)
pytest tests/ -v

# Run single test file
pytest tests/integration/test_integration.py -v

# Run specific test class/method
pytest tests/integration/test_integration.py::TestRiskAssessment::test_high_risk_fuel_engine_running -v

# Run demo scripts (in demos/ directory)
python demos/demo_position_impact.py           # Position impact analysis demo
python demos/demo_flight_impact.py             # Flight impact prediction demo

# Run interactive mode (requires LLM API key)
python apps/run_agent.py

# Start API server
python -m apps.api.main
# Or: uvicorn apps.api.main:app --reload

# Linting
black . --line-length 100
isort .
mypy .
```

## Project Structure

```
airport-emergency-agent/
├── agent/           # Core agent (ReAct + FSM)
│   ├── graph.py     # LangGraph state machine
│   ├── state.py     # AgentState TypedDict
│   └── nodes/       # Graph nodes (reasoning, tool_executor, etc.)
├── tools/           # Tool system
│   ├── registry.py  # Tool registration
│   ├── base.py      # BaseTool class
│   ├── information/ # Info query tools
│   ├── spatial/     # Topology analysis tools
│   ├── knowledge/   # RAG knowledge retrieval
│   ├── assessment/  # Risk assessment
│   └── action/      # Action tools (notify, report)
├── tests/           # Test files (pytest auto-discovery)
├── demos/           # Demo scripts
├── docs/            # Documentation and design docs
├── scenarios/       # Scenario configurations (prompt.yaml)
├── constraints/     # Constraint definitions
├── fsm/             # Finite State Machine definitions
├── apps/            # Entry points (CLI + API)
├── config/          # Configuration files
├── data/            # Data files
├── outputs/         # Generated reports
├── scripts/         # Data processing scripts (offline)
├── Radiotelephony_ATC.json  # Aviation radio telephony normalization rules
└── BSRC.json        # Bird strike risk classification rules
```

## Environment Setup

Copy `.env.example` to `.env` and configure:
- `LLM_PROVIDER`: `zhipu` or `openai`
- `LLM_MODEL`: Model name (e.g., `glm-4`)
- `LLM_API_KEY`: Your API key

## Architecture

### Hybrid Design: ReAct + FSM

```
User Input → Input Parser → ReAct Reasoning Loop → FSM Validation → Output Report
                                    ↓
                              Tool Execution
                         (deterministic engines)
```

**Key principle**: LLM handles flexible reasoning and decision-making, while deterministic components (rule engine, graph algorithms) handle calculations that require precision.

## Detailed Data Flow

### User Input → Entity Extraction Flow

```python
# agent/nodes/input_parser.py

User Input (Chinese text)
    ↓
┌─────────────────────────────────────────────────────┐
│ 1. normalize_radiotelephony_text()                  │
│    基础规范化: 洞→0, 幺→1, 拐→7                      │
│    跑道方向标识: 跑道27左→跑道27L (ICAO格式)         │
│    从 Radiotelephony_ATC.json 加载规则              │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ 2. RadiotelephonyNormalizer (LLM + 规则检索)         │
│    ├─ retrieve_examples()                           │
│    │  # 关键词匹配检索 Few-shot 示例                 │
│    │  # 提取: runway, taxiway, stand, flight        │
│    ├─ _build_prompt()                               │
│    │  # 构建 Few-shot 提示词                         │
│    ├─ LLM.invoke()                                  │
│    │  # 语义规范化 (5秒超时)                         │
│    └─ 返回 {                                        │
│          normalized_text,                           │
│          entities {flight_no, position, ...},       │
│          confidence                                 │
│       }                                             │
└─────────────────────────────────────────────────────┘
    ↓
identify_scenario()
    # Match keywords against ScenarioRegistry
    # Returns: "oil_spill", "bird_strike", etc.
    ↓
extract_entities_hybrid()
    ├─ Fast path: Regex patterns
    │  # Extracts: position, fluid_type, engine_status, flight_no
    │  # Bird strike adds: event_type, affected_part, current_status,
    │  # phase, evidence, bird_info, ops_impact (from manifest regex)
    │  # Patterns: r'[A-Z]{2,3}\d{3,4}', r'(燃油|滑油|液压油)', etc.
    ├─ Flex path: LLM semantic extraction
    │  # Handles ambiguous natural language
    │  # Example: "右侧发动机漏油" → {side: "right", fluid_type: "OIL"}
    └─ Merge: Normalizer entities > Regex > LLM
    ↓
Optional: understand_conversation() [if ENABLE_SEMANTIC_UNDERSTANDING=true]
    ├─ Extract facts from conversation context
    ├─ Confidence scoring per entity
    ├─ Split into accepted/low-confidence
    └─ Detect semantic issues (conflicts, ambiguities)
    ↓
apply_auto_enrichment()  # 🔄 Parallel execution
    ├─ Phase 1: Independent queries (ThreadPoolExecutor, max 3 workers)
    │  ├─ get_aircraft_info(flight_no) → aircraft details
    │  ├─ flight_plan_lookup(flight_no) → flight schedule
    │  └─ get_stand_location(position) → stand coordinates + topology
    │
    ├─ Phase 2: Dependent calculations (requires Phase 1 results)
    │  ├─ calculate_impact_zone(position, fluid_type, risk_level)
    │  │  # BFS graph diffusion algorithm
    │  │  # Rules: FUEL HIGH=3 hops, MEDIUM=2 hops, etc.
    │  └─ analyze_position_impact(position)
    │     # Direct impact analysis + adjacent facilities
    │
    └─ Timeout handling: 10s per future, graceful degradation
    ↓
update_checklist()
    # Mark collected fields as complete in state.checklist
    ↓
Output: Updated AgentState
    ├─ incident: enriched with auto-fetched data
    ├─ checklist: {fluid_type: true, position: true, ...}
    ├─ spatial_analysis: {affected_taxiways, affected_runways, ...}
    ├─ flight_plan_table: flight schedule data
    └─ observations: enrichment process records

### Bird Strike Checklist Fields

Bird strike adds P2 fields for risk assessment accuracy:
- `phase` (flight phase)
- `evidence` (evidence strength)
- `bird_info` (bird characteristics)
- `ops_impact` (operational impact)

See `scenarios/bird_strike/checklist.yaml` and `docs/SCENARIO_FIELD_CONTRACTS.md`.

### Bird Strike Risk Assessment (BSRC)

```python
# tools/assessment/assess_bird_strike_risk.py

incident (phase, affected_part, event_type, current_status, crew_request, ...)
    ↓
assess_bird_strike_risk.execute()
    ├─ Normalize inputs: phase/impact_area/evidence/bird_info/ops_impact
    ├─ Weighted score + rule boosts (BSRC.json)
    ├─ Apply risk floor overrides (R1-R4)
    └─ Update state.risk_assessment + mandatory_actions_done.risk_assessed
```
```

### Risk Assessment → Spatial Analysis Flow

```python
# tools/assessment/assess_risk.py

Current incident (fluid_type, engine_status, continuous, leak_size)
    ↓
assess_risk_tool.execute()
    ├─ Load rules from scenario or defaults
    ├─ Match against RISK_RULES (priority-ordered, 12 rules):
    │  1. (FUEL + continuous + RUNNING) → HIGH (95 pts)
    │  2. (FUEL + RUNNING) → HIGH (90 pts)
    │  3. (FUEL + continuous) → HIGH (85 pts)
    │  ...
    │  12. (OIL) → LOW (25 pts)
    │
    ├─ Return: {level, score, factors, immediate_actions}
    │  # level: "HIGH", "MEDIUM_HIGH", "MEDIUM", "LOW"
    │  # score: 0-100 numerical score
    │  # factors: ["航空燃油", "发动机运转", ...]
    │  # immediate_actions: ["关闭发动机", "泡沫覆盖", ...]
    │
    └─ Update state.risk_assessment
    ↓
calculate_impact_zone_tool.execute()
    ├─ Load airport topology (NetworkX graph from JSON)
    │  # Nodes: stands, taxiways, runways with lat/lon
    │  # Edges: connectivity between nodes
    │
    ├─ Find start node (nearest to position)
    │
    ├─ Look up spread rule from SPREAD_RULES
    │  FUEL:
    │    HIGH: radius=3, runway_impact=true
    │    MEDIUM: radius=2, runway_impact=true
    │    LOW: radius=1, runway_impact=false
    │  HYDRAULIC: radius=2/1/1, no runway
    │  OIL: radius=1/1/0
    │
    ├─ BFS spread from start node (breadth-first search)
    │  # Explore graph up to radius hops
    │
    ├─ Classify nodes: taxiway | runway | stand
    │
    ├─ Check runway adjacency (if rule.runway_impact)
    │
    └─ Return: {isolated_nodes, affected_taxiways, affected_runways}
    ↓
analyze_position_impact_tool.execute()
    ├─ Analyze direct impact on facility
    ├─ Estimate closure time (based on fluid type + risk level)
    ├─ Calculate severity score (1-10)
    └─ Identify adjacent affected facilities
    ↓
predict_flight_impact_tool.execute() [⚠️ Partially implemented]
    ├─ Query flight plan database
    ├─ Match flights to affected stands/runways/taxiways
    ├─ Calculate delay predictions
    └─ Generate severity distribution
```

### FSM Validation → Mandatory Actions Flow

```python
# agent/nodes/fsm_validator.py

AgentState (after critical tool execution: assess_risk, calculate_impact_zone, notify_department)
    ↓
fsm_validator_node()
    ├─ Get validator: FSMValidator(FSMEngine)
    │
    ├─ Call validate(agent_state):
    │  ├─ sync_with_agent_state()
    │  │  # Infer current FSM state from Agent completion
    │  │  # Example: checklist.p1_complete=true → P1_RISK_ASSESS
    │  │            mandatory.risk_assessed=true → P2_IMMEDIATE_CONTROL
    │  │
    │  ├─ check_preconditions(target_state, agent_state)
    │  │  # For each precondition (e.g., "checklist.fluid_type"):
    │  │  #   Check if satisfied; add error if not
    │  │  # Example: Entering P2 requires mandatory.risk_assessed=true
    │  │
    │  └─ check_mandatory_actions(agent_state)
    │     ├─ For each MandatoryAction:
    │     │  ├─ Evaluate condition (e.g., risk_level == "HIGH")
    │     │  ├─ If triggered: check if completed
    │     │  └─ If not completed: add to pending_actions
    │     │
    │     # Example:
    │     # Condition: risk_level == "HIGH"
    │     # Action: notify_department(department: 消防, priority: immediate)
    │     # Check field: fire_dept_notified
    │     #
    │     └─ Return (errors, pending_actions)
    │
    └─ Return: FSMValidationResult
       ├─ is_valid: boolean
       ├─ current_state: FSM state before validation
       ├─ inferred_state: FSM state after validation
       ├─ errors: ["进入P2需要先完成risk_assessed", ...]
       └─ pending_actions: [{action: "notify_department", params: {...}}, ...]
    ↓
Routing decision (after_fsm_validation):
    ├─ If errors: → reasoning (Agent needs to fix)
    │  # FSM error messages guide Agent remediation
    │  # Example: "高危情况必须通知消防" → Agent calls notify_department
    │
    ├─ If COMPLETED state: → output_generator
    │
    ├─ If P8_CLOSE + pending_actions: → reasoning (trigger forced actions)
    │
    └─ Otherwise: → reasoning (continue)
```

### Report Generation → Final Output Flow

```python
# agent/nodes/output_generator.py

Complete AgentState
    ↓
output_generator_node()
    ├─ Build affected areas text (from spatial_analysis)
    │  # Format: "501机位、滑行道A1/A2、跑道09"
    │
    ├─ Build event context
    │  ├─ incident: position, fluid_type, engine_status, continuous
    │  ├─ risk_assessment: level, score, factors
    │  └─ spatial_analysis: impact zone, affected facilities
    │
    ├─ Collect handling process (from actions_taken)
    │  # Timeline of tool executions with timestamps
    │  # Example: [
    │  #   "14:30 - 风险评估：HIGH级风险（90分）",
    │  #   "14:32 - 通知消防部门：已到达现场",
    │  #   ...
    │  # ]
    │
    ├─ Collect notifications sent
    │  # List of notified departments with priority
    │
    ├─ Prepare recommendations (based on risk level)
    │  # HIGH: "立即关闭发动机", "泡沫覆盖", ...
    │  # MEDIUM: "清污人员就位", "防滑处理", ...
    │
    ├─ Call LLM to generate summary (optional)
    │  # Narrative summary of incident handling
    │
    ├─ Render final report from template [⚠️ Currently: 778-line string concatenation]
    │  # Report structure:
    │  #   - Title, event summary, risk level
    │  #   - Handling process (timeline of actions)
    │  #   - Checklist items (P1/P2 fields)
    │  #   - Coordination units notified
    │  #   - Operational impact (affected flights, closure time)
    │  #   - Recommendations (safety measures, follow-up)
    │  #   - Timestamp
    │
    └─ Return: final_report (dict) + final_answer (str)
    ↓
tool_executor_node() [if generate_report action]
    ├─ Detect report_generated flag
    ├─ Call output_generator_node()
    ├─ Set awaiting_user = True
    ├─ Set next_node = "end"
    └─ Wait for user confirmation
```

### Core Components

**LangGraph State Machine** (`agent/graph.py`):
- Defines the agent workflow as a directed graph
- Entry: `input_parser` → `reasoning` → conditional routing
- Key routing functions: `should_continue()`, `after_tool_execution()`, `after_fsm_validation()`

**Agent State** (`agent/state.py`):
- `AgentState` TypedDict containing: incident info, checklist status, FSM state, risk assessment, spatial analysis
- `FSMState` enum: INIT → P1_RISK_ASSESS → P2_IMMEDIATE_CONTROL → ... → P8_CLOSE → COMPLETED
- `create_initial_state()` factory function

**Node Implementations** (`agent/nodes/`):
- `input_parser.py`: Entity extraction from Chinese text (position, fluid type, engine status). Implements **two-stage radiotelephony normalization**:
  1. Basic rule-based conversion (洞→0, 幺→1, 拐→7)
  2. LLM + rule-based Few-shot retrieval (not vector RAG)
  Automatically retrieves flight info from `data/raw/航班计划/Log_*.txt` and performs topology analysis from `scripts/data_processing/topology_clustering_based.json`.
- `reasoning.py`: ReAct loop with `build_scenario_prompt()` for dynamic prompt loading. Displays flight information (airline, stand, runway, flight type) and topology analysis results (impact zone, affected taxiways/runways) in context summary.
- `tool_executor.py`: Executes tools from registry
- `fsm_validator.py`: Validates state transitions and mandatory actions
- `output_generator.py`: Generates final reports

### Scenario-Specific Prompts

**Dynamic Prompt Loading** (`scenarios/base.py`, `agent/nodes/reasoning.py`):
- Each scenario has `prompt.yaml` defining its system prompt and field collection order
- `build_scenario_prompt()` function dynamically loads scenario configuration
- `ScenarioRegistry` manages scenario registration and retrieval
- Fields are collected in the order defined by `field_order` in each scenario's prompt.yaml

**Prompt Configuration** (`scenarios/<scenario>/prompt.yaml`):
```yaml
system_prompt: |
  你是机场机坪应急响应专家 Agent...

field_order:           # 信息收集顺序（强制按序询问）
  - flight_no
  - position
  - fluid_type
  - engine_status
  - continuous

field_names:           # 字段中文名称映射
  flight_no: 航班号
  position: 事发位置

ask_prompts:           # 各字段的追问提示
  flight_no: "请提供涉事飞机的航班号？"
  position: "请报告事件发生的具体位置？"
```

### Tool System

**Tool Registry** (`tools/registry.py`):
- Tools registered with scenario tags (e.g., `["oil_spill", "common"]`)
- `ToolRegistry.get_by_scenario()` returns scenario-specific tools

**Tool Categories**:
- `information/`: `ask_for_detail`, `get_aircraft_info` (automatically called when flight number is detected), `radiotelephony_normalizer` (ATC phonetic normalization)
- `spatial/`: `get_stand_location`, `calculate_impact_zone` (graph-based BFS diffusion, automatically called when position is detected)
- `knowledge/`: `search_regulations` (RAG-style retrieval)
- `assessment/`: `assess_risk` (rule-based deterministic scoring)
- `action/`: `notify_department`, `generate_report`

**Knowledge Base** (`tools/knowledge/search_regulations.py`):
- Mock knowledge base with emergency procedures for fuel, hydraulic, and engine oil spills
- Each regulation includes: risk level, risk features, cleanup method, source
- Report generator references retrieved knowledge when generating reports

**Creating New Tools**: Extend `BaseTool` from `tools/base.py`, implement `execute(state, inputs)` method, register in `tools/registry.py`.

### Risk Assessment Rules

**Fluid Type Risk Matrix** (`tools/assessment/assess_risk.py`):
| Fluid Type | Risk Level | Key Features | Cleanup Method |
|------------|------------|--------------|----------------|
| Aviation Fuel (FUEL) | HIGH | Flammable/explosive, foam coverage required | Absorbent materials + explosion-proof pump |
| Hydraulic Oil | MEDIUM-HIGH | Flammable, high-pressure jet hazard | Pressure relief first, then absorbent |
| Engine Oil (OIL) | MEDIUM | Combustible, toxic smoke | Absorbent materials + industrial cleaner |

**Immediate Actions by Risk Level**:
- HIGH: Notify fire department, shut down engine, evacuate, establish safety zone, foam coverage
- MEDIUM-HIGH: Fire department on standby, pressure relief, set up warning zone
- MEDIUM: Standby resources, absorbent materials, anti-slip treatment
- LOW: Maintenance notification, monitoring

### Constraint System

**Checklist** (`agent/state.py`):
- P1 fields (must collect): fluid_type, continuous, engine_status, position
- P2 fields: leak_size

**Mandatory Actions**:
- `risk_assessed`: Must be done before proceeding
- `fire_dept_notified`: Required for HIGH risk
- `atc_notified`: Required for certain scenarios

**FSM Validation** triggers after critical tool executions: `assess_risk`, `calculate_impact_zone`, `notify_department`

### Topology Analysis

**Airport Topology Graph** (`tools/spatial/topology_loader.py`):
- Loaded from `scripts/data_processing/topology_clustering_based.json` (generated from trajectory clustering)
- Nodes: stands, taxiways, runways with lat/lon coordinates
- Edges: connectivity between nodes (undirected graph)
- BFS-based reachability analysis for impact zone calculation

**Automatic Analysis** (`agent/nodes/input_parser.py`):
- When position is extracted → `get_stand_location` called automatically
- Location details: coordinates, adjacent taxiways, nearest runway
- Impact zone calculation: BFS diffusion based on fluid type and risk level
- Results stored in `spatial_analysis` and `incident.impact_zone`

**Impact Zone Rules** (`tools/spatial/calculate_impact_zone.py`):
| Fluid Type | Risk Level | BFS Radius | Runway Impact |
|------------|------------|------------|---------------|
| FUEL | HIGH | 3 hops | Yes |
| FUEL | MEDIUM | 2 hops | Yes |
| FUEL | LOW | 1 hop | No |
| HYDRAULIC | HIGH/MEDIUM | 2 hops | No |
| OIL | HIGH/MEDIUM | 1 hop | No |

### Radiotelephony Normalization

**Overview**: Converts aviation radio telephony (ATC phonetic alphabet) to standard format using a two-stage approach.

**Implementation** (`tools/information/radiotelephony_normalizer.py`):

```python
# Stage 1: Basic rule-based normalization (agent/nodes/input_parser.py:135-175)
def normalize_radiotelephony_text(text: str) -> str:
    """
    基础规范化: 数字和字母读法转换
    - 洞→0, 幺→1, 两→2, 三→3, 拐→7, 八→8, 九→9
    - 阿尔法→A, 布拉沃→B, 查理→C
    - 规范化位置顺序: "12滑行道" → "滑行道12"
    - 跑道方向标识转换: "跑道27左" → "跑道27L" (ICAO格式)
      # 避免"跑道27左发生鸟击"被误解析为"跑道27"+"左发"
    """
    # 从 Radiotelephony_ATC.json 加载规则
    digits_map = {"洞": "0", "幺": "1", "拐": "7", ...}
    letters_map = {"阿尔法": "A", "布拉沃": "B", ...}
    # ... 执行替换

    # 跑道方向标识转换 (左→L, 右→R, 中→C)
    normalized = re.sub(
        r"(跑道\d{1,2})(左|右|中)",
        lambda m: f"{m.group(1)}{'L' if m.group(2) == '左' else 'R' if m.group(2) == '右' else 'C'}",
        normalized,
    )
```

```python
# Stage 2: LLM + Rule-based Few-shot retrieval (tools/information/radiotelephony_normalizer.py:31-238)
class RadiotelephonyNormalizer:
    """
    航空读法规范化引擎 (LLM + 规则检索，非向量 RAG)

    工作流程:
    1. retrieve_examples(input_text)
       - 关键词匹配: 提取 runway/taxiway/stand/flight/oil_spill/bird_strike
       - 规则相似度: 基于关键词重叠度打分 (非向量相似度)
       - 返回 top-3 最相似示例

    2. _build_prompt(text, examples)
       - 加载转换规则从 Radiotelephony_ATC.json
       - 构建 Few-shot 提示词

    3. normalize_with_llm(text, timeout=5)
       - 调用 LLM 进行语义规范化
       - 返回标准化实体和置信度

    注意: 当前实现使用关键词匹配，不是真正的向量 RAG
    """

    def retrieve_examples(self, input_text: str, top_k: int = 3):
        """检索最相似的规范化示例 (基于关键词，非向量)"""
        keywords = self._extract_keywords(input_text)
        # 关键词: ["runway", "taxiway", "stand", "flight", "oil_spill", "bird_strike"]

        for example in examples:
            score = self._calculate_similarity(keywords, example["input"])
            # 规则打分: 关键词命中 +1 分
        return top_k_examples

    def normalize_with_llm(self, text: str, timeout: int = 5):
        """使用 LLM 进行语义规范化"""
        examples = self.retrieve_examples(text, top_k=3)
        prompt = self._build_prompt(text, examples)

        response = self.llm.invoke(prompt, timeout=timeout)
        result = self._parse_llm_response(response.content)

        return {
            "normalized_text": "川航3U3177 跑道02L 报告鸟击",
            "entities": {
                "flight_no": "3U3177",
                "position": "02L",
                "event_type": "bird_strike"
            },
            "confidence": 0.95
        }
```

**Knowledge Base** (`Radiotelephony_ATC.json`):

```json
{
  "digits": {
    "0": "洞", "1": "幺", "2": "两", "7": "拐", ...
  },
  "letters": {
    "A": "阿尔法", "B": "布拉沃", "C": "查理", ...
  },
  "normalization_rules": {
    "runway_formats": {
      "examples": [
        {"input": "跑道洞两左", "output": "02L"},
        {"input": "跑道幺八右", "output": "18R"}
      ]
    },
    "flight_formats": {
      "airline_codes": {
        "川航": "3U", "国航": "CA", "东航": "MU", ...
      }
    }
  }
}
```

**Integration in Input Parser** (`agent/nodes/input_parser.py:570-586`):

```python
# 步骤 1: 基础规范化
normalized_message = normalize_radiotelephony_text(user_message)
# "川航三幺拐拐 跑道洞两左" → "川航3U3177 跑道02L"

# 步骤 2: LLM + 规则深度规范化
normalizer = RadiotelephonyNormalizerTool()
normalization_result = normalizer.execute(state, {"text": normalized_message})
enhanced_message = normalization_result["normalized_text"]
pre_extracted_entities = normalization_result["entities"]
# {
#   "flight_no": "3U3177",
#   "position": "02L",
#   "event_type": "bird_strike"
# }

# 步骤 3: 合并到实体提取结果
extracted = extract_entities_hybrid(enhanced_message, history, scenario_type)
extracted.update(pre_extracted_entities)  # Normalizer entities 优先级最高
```

**Design Notes**:

- **Current Implementation**: Rule-based keyword matching (not vector RAG)
  - ✅ Fast, no external dependencies
  - ✅ Sufficient for structured aviation data
  - ⚠️ Requires manual rule updates for new patterns

- **Runway Direction Disambiguation** (跑道方向标识转换):
  - 问题: "跑道两拐左发生鸟击" 会被误解析为 position="跑道27" + affected_part="左发"
  - 解决: 在 Stage 1 预处理时将 "跑道XX左/右/中" 转换为 ICAO 格式 "跑道XXL/R/C"
  - 效果: "跑道27L发生鸟击" 中的 "L" 不再与 "左发" 正则冲突

- **Future Enhancement**: True vector-based RAG
  - Requires: embedding model (e.g., sentence-transformers) + vector DB (Chroma/FAISS)
  - Pros: Better semantic understanding, automatic pattern learning
  - Cons: Additional dependencies, higher latency
  - Decision: Defer until rule coverage proves insufficient

**Examples**:

| Input | Output | Entities |
|-------|--------|----------|
| 川航三幺拐拐 跑道洞两左 报告鸟击 | 川航3U3177 跑道02L 报告鸟击 | {flight_no: "3U3177", position: "02L", event_type: "bird_strike"} |
| 跑道两拐左发生确认鸟击 | 跑道27L发生确认鸟击 | {position: "跑道27L", event_type: "确认鸟击"} |
| 跑道27L发生鸟击 左发受损 | 跑道27L发生鸟击 左发受损 | {position: "跑道27L", affected_part: "左发"} |
| 五洞幺机位发现燃油泄漏 | 501机位发现燃油泄漏 | {position: "501", fluid_type: "FUEL"} |
| 滑行道A三有液压油 | 滑行道A3有液压油 | {position: "A3", fluid_type: "HYDRAULIC"} |

### LLM Configuration

`config/llm_config.py`:
- `LLMClientFactory` supports zhipu (GLM-4) and OpenAI-compatible APIs
- Uses LangChain's `ChatOpenAI` or `ChatZhipuAI`

## Supported Scenarios

- `oil_spill` (implemented): Fuel/hydraulic/oil leak handling with dedicated prompt.yaml
- `bird_strike` (example): Bird strike scenario with prompt.yaml (template for new scenarios)
- `tire_burst`, `runway_incursion` (planned)

**Adding New Scenarios**:
1. Create `scenarios/<name>/` directory with `prompt.yaml`
2. Register scenario class in `scenarios/base.py`
3. Optionally add `config.yaml`, `checklist.yaml`, `fsm_states.yaml`

See `scenarios/SCENARIO_GUIDE.md` for detailed instructions.

## API Endpoints

- `POST /event/start`: Start new incident session
- `POST /event/chat`: Continue conversation in session
- `GET /event/{session_id}`: Get session status
- `GET /event/{session_id}/report`: Get generated report
- `DELETE /event/{session_id}`: Close session

See [API Documentation](./docs/API_DOCUMENTATION.md) for detailed schemas and examples.

## Tool Development Guide

### Creating a New Tool

**Step 1: Create tool file**

```python
# tools/category/my_tool.py

from typing import Dict, Any
from tools.base import BaseTool

class MyTool(BaseTool):
    """
    Brief description of what this tool does.

    This tool should be used when...
    """

    # Tool metadata
    name = "my_tool"
    description = "Clear description visible to LLM for tool selection"

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool logic.

        Args:
            state: Current AgentState dict
            inputs: Action inputs from LLM (action_input field)

        Returns:
            Dict with keys:
                - observation: String message shown to Agent
                - success: Boolean indicating success/failure
                - (optional) Additional state updates
        """
        # Extract inputs
        param1 = inputs.get("param1")
        param2 = inputs.get("param2", "default_value")

        # Validate inputs
        if not param1:
            return {
                "observation": "Error: param1 is required",
                "success": False
            }

        # Execute tool logic
        try:
            result = self._do_work(param1, param2)

            return {
                "observation": f"Successfully completed: {result}",
                "success": True,
                # Optional: Update state
                "state_updates": {
                    "my_data": result
                }
            }
        except Exception as e:
            return {
                "observation": f"Tool execution failed: {str(e)}",
                "success": False
            }

    def _do_work(self, param1: str, param2: str) -> Any:
        """Private helper method for actual work."""
        # Implementation here
        return "result"
```

**Step 2: Register tool in registry**

```python
# tools/registry.py

from tools.category.my_tool import MyTool

def register_all_tools():
    """Register all tools with the ToolRegistry."""

    # ... existing registrations ...

    # Register your tool
    ToolRegistry.register(
        MyTool(),
        scenarios=["oil_spill", "common"]  # Which scenarios can use this tool
    )
```

**Step 3: Add tests**

```python
# tests/tools/test_my_tool.py

import pytest
from tools.category.my_tool import MyTool

class TestMyTool:
    def test_execute_success(self):
        tool = MyTool()
        state = {"incident": {...}}
        inputs = {"param1": "value1"}

        result = tool.execute(state, inputs)

        assert result["success"] is True
        assert "Successfully completed" in result["observation"]

    def test_execute_missing_param(self):
        tool = MyTool()
        state = {}
        inputs = {}  # Missing param1

        result = tool.execute(state, inputs)

        assert result["success"] is False
        assert "param1 is required" in result["observation"]
```

### Tool Categories

Tools are organized by category:

- **information/**: Query tools that gather data
  - `ask_for_detail`: Ask user for specific field
  - `get_aircraft_info`: Retrieve flight information
  - `radiotelephony_normalizer`: Convert ATC phonetic alphabet to standard format (e.g., "洞"→"0", "幺"→"1", "拐"→"7")
  - `smart_ask`: Intelligently ask multiple questions

- **spatial/**: Topology and geography analysis
  - `get_stand_location`: Find stand coordinates
  - `calculate_impact_zone`: BFS diffusion algorithm

- **knowledge/**: Knowledge base retrieval
  - `search_regulations`: RAG-style regulation lookup

- **assessment/**: Risk and impact evaluation
  - `assess_risk`: Rule-based risk scoring

- **action/**: External actions
  - `notify_department`: Send notifications
  - `generate_report`: Create final report

### Tool Best Practices

1. **Clear naming**: Tool name should be action-oriented (`get_`, `calculate_`, `assess_`)

2. **Descriptive description**: LLM uses this to decide when to use the tool

3. **Input validation**: Always validate inputs before execution

4. **Error handling**: Return structured error messages in `observation`

5. **State updates**: Return `state_updates` dict to modify AgentState

6. **Deterministic when possible**: Avoid LLM calls in tools for calculable logic

7. **Idempotent**: Tools should be safe to call multiple times

### Example: Creating "Get Weather" Tool

```python
# tools/information/get_weather.py

from typing import Dict, Any
import requests
from tools.base import BaseTool

class GetWeatherTool(BaseTool):
    """
    Retrieves current weather conditions for a location.
    Use this tool when you need weather information to assess
    environmental impact on incident handling.
    """

    name = "get_weather"
    description = "Get current weather conditions (temperature, wind, precipitation) for a specific location"

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        location = inputs.get("location")

        if not location:
            return {
                "observation": "Error: Location parameter is required",
                "success": False
            }

        try:
            # Call weather API (example)
            weather_data = self._fetch_weather(location)

            observation = (
                f"Weather at {location}:\n"
                f"- Temperature: {weather_data['temp']}°C\n"
                f"- Wind: {weather_data['wind_speed']} m/s, {weather_data['wind_direction']}\n"
                f"- Conditions: {weather_data['conditions']}"
            )

            return {
                "observation": observation,
                "success": True,
                "state_updates": {
                    "weather": weather_data
                }
            }
        except Exception as e:
            return {
                "observation": f"Failed to fetch weather: {str(e)}",
                "success": False
            }

    def _fetch_weather(self, location: str) -> Dict[str, Any]:
        # Actual API call implementation
        return {
            "temp": 25,
            "wind_speed": 5,
            "wind_direction": "NE",
            "conditions": "Clear"
        }

# Register in tools/registry.py:
# ToolRegistry.register(GetWeatherTool(), scenarios=["oil_spill", "common"])
```

## Code Quality Guidelines

### Error Handling Patterns

**Good: Specific exception handling**
```python
try:
    result = tool.execute(state, inputs)
except ToolExecutionError as e:
    logger.error(f"Tool execution failed: {e}", exc_info=True)
    return {"observation": f"Error: {e}", "success": False}
except ValidationError as e:
    logger.warning(f"Invalid input: {e}")
    return {"observation": f"Invalid input: {e}", "success": False}
```

**Bad: Catching all exceptions silently**
```python
try:
    result = tool.execute(state, inputs)
except:  # Too broad, hides bugs
    pass  # Silent failure - never do this!
```

### Logging Best Practices

Add logging to critical paths:

```python
import logging
logger = logging.getLogger(__name__)

def input_parser_node(state: AgentState) -> AgentState:
    logger.info(f"Starting input parsing for session {state['session_id']}")

    entities = extract_entities_hybrid(message)
    logger.debug(f"Extracted entities: {entities}")

    if not entities.get("position"):
        logger.warning("Position not extracted from user input")

    return updated_state
```

**Log levels:**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages (state transitions, tool executions)
- `WARNING`: Unexpected situations that don't block execution
- `ERROR`: Error events that may still allow continued operation
- `CRITICAL`: Severe errors causing system failure

### Type Annotation Requirements

All functions must have type hints:

```python
# Good
def calculate_risk(
    fluid_type: str,
    engine_status: str,
    continuous: bool
) -> RiskAssessment:
    ...

# Bad
def calculate_risk(fluid_type, engine_status, continuous):
    ...
```

Use TypedDict for complex dictionaries:

```python
from typing import TypedDict

class ToolResult(TypedDict):
    observation: str
    success: bool
    state_updates: Dict[str, Any]
```

### Testing Requirements

Every tool must have:
1. Success case test
2. Failure case test
3. Edge case tests

```python
@pytest.mark.parametrize("fluid_type,expected_level", [
    ("FUEL", "HIGH"),
    ("HYDRAULIC", "MEDIUM"),
    ("OIL", "LOW"),
])
def test_assess_risk_levels(fluid_type, expected_level):
    ...
```

## Production Readiness Checklist

### Must-Have (Blocking Production)

- [ ] **Persistent storage** (PostgreSQL/Redis) for sessions
- [ ] **Docker containerization** with docker-compose
- [ ] **Structured logging** (JSON format) in all critical paths
- [ ] **Health check endpoint** (`/health` with liveness + readiness)
- [ ] **Basic metrics** (request count, response time, active sessions)
- [ ] **Database for reports** (replace file-based storage)
- [ ] **API authentication** (API key or JWT)
- [ ] **Secrets management** (remove hardcoded API keys)

### Should-Have (High Priority)

- [ ] **Configuration profiles** (dev/staging/prod separation)
- [ ] **Comprehensive error handling** (custom exception hierarchy)
- [ ] **Input validation middleware** (centralized validation)
- [ ] **Rate limiting** (per-IP request throttling)
- [ ] **CI/CD pipeline** (GitHub Actions for test + deploy)
- [ ] **Test coverage reporting** (pytest-cov with 80%+ target)
- [ ] **API documentation** (OpenAPI/Swagger specs)

### Nice-to-Have (Enhancement)

- [ ] **Caching layer** (Redis for frequent queries)
- [ ] **Message queue** (Celery/RabbitMQ for async processing)
- [ ] **Distributed tracing** (Jaeger/Datadog integration)
- [ ] **Custom Prometheus metrics** (business-specific metrics)
- [ ] **Multi-language support** (i18n for prompts and reports)
- [ ] **Automated rollback** (blue-green deployment)

Current Status: **45% production-ready** (Early Beta)

See [Production Readiness Assessment](./docs/PRODUCTION_READINESS.md) for detailed analysis.

## Troubleshooting Guide

### Common Issues

**Issue: "Tool not found: xyz"**
- **Cause**: Tool not registered in ToolRegistry or typo in tool name
- **Solution**: Check `tools/registry.py` registration, ensure tool name matches

**Issue: Session data lost after restart**
- **Cause**: Using MemorySessionStore (in-memory only)
- **Solution**: Implement PostgreSQL session store (see DEPLOYMENT_GUIDE.md)

**Issue: LLM output parsing fails**
- **Cause**: LLM returned non-JSON or malformed JSON
- **Solution**: Check `reasoning.py` fallback extraction logic, review system prompt

**Issue: FSM validation errors block progress**
- **Cause**: Mandatory actions not completed or preconditions not met
- **Solution**: Check `validation_result.errors` in Agent context, complete required actions

**Issue: Spatial analysis returns empty impact zone**
- **Cause**: Position not found in topology graph or invalid position format
- **Solution**: Verify position exists in `scripts/data_processing/topology_clustering_based.json`

### Debugging Tips

**Enable verbose logging:**
```bash
# In .env
LOG_LEVEL=DEBUG
```

**Enable LangSmith tracing:**
```bash
# In .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=aero-agent-dev
```

**Check session state:**
```python
# In terminal/debugging
from apps.api.session_store import get_session_store

store = get_session_store()
state = store.get("session_id_here")
print(state)
```

**Test individual tools:**
```bash
pytest tests/tools/test_assess_risk.py -v -s
```

**Validate topology data:**
```python
from tools/spatial/topology_loader import load_topology

graph = load_topology()
print(f"Nodes: {graph.number_of_nodes()}")
print(f"Edges: {graph.number_of_edges()}")
print(f"Sample node: {list(graph.nodes(data=True))[0]}")
```

### Performance Tuning

**Reduce auto-enrichment latency:**
- Increase ThreadPoolExecutor workers (default: 3)
- Cache flight data in Redis
- Pre-load topology graph on startup

**Optimize LLM calls:**
- Use shorter system prompts for simple scenarios
- Cache common LLM responses
- Use streaming for long outputs

**Database optimization:**
- Index session_id column
- Use connection pooling (SQLAlchemy)
- Implement read replicas for reporting queries

### Log Locations

- **Application logs**: stdout (capture with Docker logs)
- **LangSmith traces**: https://smith.langchain.com/
- **API request logs**: Check middleware logging in `apps/api/main.py`
- **Tool execution logs**: Currently minimal - add custom logging as needed

For more help, see:
- [Deployment Guide](./docs/DEPLOYMENT_GUIDE.md)
- [Architecture Decisions](./docs/ARCHITECTURE_DECISIONS.md)
- [GitHub Issues](https://github.com/yourrepo/issues)
