# CLAUDE_DEV.md - Developer Documentation

This document contains detailed technical documentation for developers working on the Airport Emergency Response Agent system.

For high-level overview and quick start, see **CLAUDE.md**.

## Table of Contents

1. [Detailed Data Flows](#detailed-data-flows)
2. [Scenario Configuration](#scenario-configuration)
3. [Tool System Details](#tool-system-details)
4. [Risk Assessment Rules](#risk-assessment-rules)
5. [FSM System](#fsm-system)
6. [Constraint System](#constraint-system)
7. [Topology Analysis](#topology-analysis)
8. [Radiotelephony Normalization](#radiotelephony-normalization)
9. [LLM Configuration](#llm-configuration)
10. [Semantic Understanding Module](#semantic-understanding-module)
11. [Tool Development Guide](#tool-development-guide)
12. [Code Quality Guidelines](#code-quality-guidelines)
13. [Production Readiness Checklist](#production-readiness-checklist)

---

## Detailed Data Flows

### User Input → Entity Extraction Flow

```python
# agent/nodes/input_parser.py

User Input (Chinese text)
    ↓
┌─────────────────────────────────────────────────────┐
│ 1. normalize_radiotelephony_text()                  │
│    基础规范化: 洞→0, 幺→1, 拐→7                      │
│    跑道方向标识: 跑道27左→跑道27L (ICAO格式)         │
│    从 data/raw/Radiotelephony_ATC.json 加载规则     │
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
Entity extraction (depends on ENABLE_SEMANTIC_UNDERSTANDING)
    ├─ If enabled:
    │  ├─ understand_conversation() → LLM + history extraction
    │  ├─ split_by_confidence() → accepted vs low-confidence
    │  └─ deterministic extract_entities() → regex补充
    └─ If disabled:
       ├─ extract_entities_hybrid() → regex + LLM
       └─ Merge: Normalizer entities > Hybrid extraction
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
```

### Automatic Weather Query Flow

```
Position known → reasoning_node auto trigger → tool_executor(get_weather)
    ↓
get_weather(location=incident.position)
    ├─ Normalize location (e.g., 跑道27L → 27L)
    ├─ Query latest record from data/processed/awos_weather_*.csv
    └─ If missing: fallback to nearest observation point with warning
```

- Weather is queried once per position (repeat only if position changes)
- If input text indicates a runway, `position_display` keeps the "跑道" prefix for UI/report output

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
    │  #   "14:30 - 风险评估:HIGH级风险(90分)",
    │  #   "14:32 - 通知消防部门:已到达现场",
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

---

## Scenario Configuration

### Dynamic Prompt Loading

Each scenario has `prompt.yaml` defining its system prompt and field collection order:

```yaml
# scenarios/oil_spill/prompt.yaml

system_prompt: |
  你是机场机坪应急响应专家 Agent...

field_order:           # 信息收集顺序(强制按序询问)
  - flight_no
  - position
  - fluid_type
  - engine_status
  - continuous

field_names:           # 字段中文名称映射
  flight_no: 航班号
  position: 事发位置
  fluid_type: 液体类型

ask_prompts:           # 各字段的追问提示
  flight_no: "请提供涉事飞机的航班号?"
  position: "请报告事件发生的具体位置?"
  fluid_type: "请描述泄漏液体的类型?"
```

### Checklist Hierarchy

**P1 fields** (must collect before risk assessment):
- Oil spill: `fluid_type`, `continuous`, `engine_status`, `position`
- Bird strike: `flight_no`, `position`, `event_type`, `affected_part`, `current_status`, `crew_request`

**P2 fields** (optional, enhances assessment accuracy):
- Oil spill: `leak_size`
- Bird strike: `tail_no`, `phase`, `evidence`, `bird_info`, `ops_impact`

See `scenarios/bird_strike/checklist.yaml` and `docs/SCENARIO_FIELD_CONTRACTS.md`.

---

## Tool System Details

### Tool Registry

Tools are registered with scenario tags:

```python
# tools/registry.py

ToolRegistry.register(
    AssessRiskTool(),
    scenarios=["oil_spill", "common"]
)
```

`ToolRegistry.get_by_scenario("oil_spill")` returns all tools tagged with `oil_spill` or `common`.

### Tool Categories

**Information Tools (6)**:
- `ask_for_detail`: Ask user for specific missing field with context-aware prompts
- `get_aircraft_info`: Retrieve flight information from database (auto-called when flight number detected)
- `flight_plan_lookup`: Query flight schedule from `data/raw/航班计划/`
- `get_weather`: Query AWOS weather data from CSV/XLSX files
- `smart_ask`: Intelligently ask multiple related questions in one interaction
- `radiotelephony_normalizer`: ATC phonetic normalization (two-stage approach)

**Spatial Tools (5)**:
- `get_stand_location`: Find stand coordinates and adjacent facilities
- `calculate_impact_zone`: Graph-based BFS diffusion (auto-called when position detected)
- `analyze_position_impact`: Detailed impact analysis with closure time, severity score (1-10)
- `predict_flight_impact`: Flight impact prediction (⚠️ partially implemented)
- `topology_loader`: Load and manage airport topology graph (NetworkX)

**Knowledge Tools (1)**:
- `search_regulations`: RAG-style retrieval from emergency procedures knowledge base

**Assessment Tools (3)**:
- `assess_risk`: Compatibility shim for scenario-specific assessors
- `assess_oil_spill_risk`: 12-rule deterministic engine for FUEL/HYDRAULIC/OIL
- `assess_bird_strike_risk`: BSRC weighted scoring based on phase, evidence, bird characteristics

**Action Tools (2)**:
- `notify_department`: Send notifications to fire, ATC, maintenance, operations, etc.
- `generate_report`: Create final incident report with timeline and recommendations

### Knowledge Base

**Mock knowledge base** (`tools/knowledge/search_regulations.py`):
- Emergency procedures for fuel, hydraulic, and engine oil spills
- Each regulation includes: risk level, risk features, cleanup method, source
- Report generator references retrieved knowledge when generating reports

---

## Risk Assessment Rules

### Architecture Note

`tools/assessment/assess_risk.py` is a **compatibility shim** that imports scenario-specific assessment tools:
- `assess_oil_spill_risk.py` - For oil/fuel/hydraulic spills
- `assess_bird_strike_risk.py` - For bird strike incidents using BSRC rules

### Fluid Type Risk Matrix

**Oil Spill Risk Matrix** (`tools/assessment/assess_oil_spill_risk.py`):

| Fluid Type | Risk Level | Key Features | Cleanup Method |
|------------|------------|--------------|----------------|
| Aviation Fuel (FUEL) | HIGH | Flammable/explosive, foam coverage required | Absorbent materials + explosion-proof pump |
| Hydraulic Oil | MEDIUM-HIGH | Flammable, high-pressure jet hazard | Pressure relief first, then absorbent |
| Engine Oil (OIL) | MEDIUM | Combustible, toxic smoke | Absorbent materials + industrial cleaner |

### Immediate Actions by Risk Level

- **HIGH**: Notify fire department, shut down engine, evacuate, establish safety zone, foam coverage
- **MEDIUM-HIGH**: Fire department on standby, pressure relief, set up warning zone
- **MEDIUM**: Standby resources, absorbent materials, anti-slip treatment
- **LOW**: Maintenance notification, monitoring

---

## FSM System

### FSM Module Structure

```python
fsm/
├── engine.py       # FSMEngine - Core state management logic
│   ├── State transition rules
│   ├── Precondition checking
│   └── State synchronization with AgentState
├── validator.py    # FSMValidator - Validation interface
│   ├── validate(agent_state) → FSMValidationResult
│   ├── check_preconditions()
│   └── check_mandatory_actions()
├── states.py       # FSMState enum + transition definitions
│   └── INIT → P1_RISK_ASSESS → P2_IMMEDIATE_CONTROL → ... → COMPLETED
└── transitions.py  # State transition matrix
```

### FSM State Flow

```
INIT                    # Initial state
  ↓
P1_RISK_ASSESS         # Risk assessment phase (collect P1 fields)
  ↓
P2_IMMEDIATE_CONTROL   # Immediate control actions
  ↓
P3_IMPACT_ANALYSIS     # Spatial impact analysis
  ↓
P4_NOTIFICATION        # Department notifications
  ↓
P5_MONITORING          # Situation monitoring
  ↓
P6_FOLLOWUP            # Follow-up actions
  ↓
P7_REPORTING           # Report generation
  ↓
P8_CLOSE               # Incident closure
  ↓
COMPLETED              # Final state
```

### Validation Triggers

FSM validation runs after critical tool executions:
- `assess_risk` → validates risk assessment completion
- `calculate_impact_zone` → validates spatial analysis
- `notify_department` → validates notification requirements

### Validation Results

```python
FSMValidationResult:
  - is_valid: Boolean indicating compliance
  - current_state: FSM state before validation
  - inferred_state: FSM state after validation (may auto-advance)
  - errors: List of validation failures (e.g., "进入P2需要先完成risk_assessed")
  - pending_actions: List of mandatory actions not yet completed
```

---

## Constraint System

### Constraint Module Structure

```python
constraints/
├── checker.py   # ConstraintChecker - Rule evaluation engine
│   ├── check_field_constraints()   # Validate field values
│   ├── check_workflow_constraints() # Validate workflow rules
│   └── evaluate_condition()        # Dynamic rule evaluation
└── loader.py    # ConstraintLoader - Load constraints from YAML
    └── load_scenario_constraints()
```

### Mandatory Actions

Defined in `agent/state.py` + `fsm/`:
- `risk_assessed`: Must complete risk assessment before P2
- `fire_dept_notified`: Required for HIGH risk incidents
- `atc_notified`: Required for runway/taxiway impacts
- `impact_zone_calculated`: Required before notifications

### Constraint Evaluation

- Constraints loaded from `scenarios/<scenario>/config.yaml`
- Dynamic condition evaluation supports complex rules:
  ```python
  risk_level == "HIGH" AND position CONTAINS "runway"
  ```
- Violations block state transitions and trigger Agent remediation

---

## Topology Analysis

### Airport Topology Graph

**Data source** (`tools/spatial/topology_loader.py`):
- **Primary**: `scripts/data_processing/topology_clustering_based.json` (generated from trajectory clustering)
- **Alternate**: `data/spatial/airport_topology.json` (backup copy)

**Data structure**:
- Nodes: stands, taxiways, runways with lat/lon coordinates
- Edges: connectivity between nodes (undirected graph)
- NetworkX format for efficient graph algorithms

**Analysis methods**:
- BFS-based reachability analysis for impact zone calculation
- Graph diffusion with configurable radius (1-3 hops)
- Runway adjacency detection

### Automatic Analysis

When position is extracted in `input_parser.py`:
1. `get_stand_location` called automatically
2. Location details: coordinates, adjacent taxiways, nearest runway
3. Impact zone calculation: BFS diffusion based on fluid type and risk level
4. Results stored in `spatial_analysis` and `incident.impact_zone`

### Impact Zone Rules

| Fluid Type | Risk Level | BFS Radius | Runway Impact |
|------------|------------|------------|---------------|
| FUEL | HIGH | 3 hops | Yes |
| FUEL | MEDIUM | 2 hops | Yes |
| FUEL | LOW | 1 hop | No |
| HYDRAULIC | HIGH/MEDIUM | 2 hops | No |
| OIL | HIGH/MEDIUM | 1 hop | No |

---

## Radiotelephony Normalization

### Overview

Converts aviation radio telephony (ATC phonetic alphabet) to standard format using a two-stage approach.

### Implementation

**Stage 1: Basic rule-based normalization** (`agent/nodes/input_parser.py:135-175`):

```python
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

**Stage 2: LLM + Rule-based Few-shot retrieval** (`tools/information/radiotelephony_normalizer.py:31-238`):

```python
class RadiotelephonyNormalizer:
    """
    航空读法规范化引擎 (LLM + 规则检索,非向量 RAG)

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

    注意: 当前实现使用关键词匹配,不是真正的向量 RAG
    """

    def retrieve_examples(self, input_text: str, top_k: int = 3):
        """检索最相似的规范化示例 (基于关键词,非向量)"""
        keywords = self._extract_keywords(input_text)
        # 关键词: ["runway", "taxiway", "stand", "flight", "oil_spill", "bird_strike"]

        for example in examples:
            score = self._calculate_similarity(keywords, example["input"])
            # 规则打分: 关键词命中 +1 分
        return top_k_examples
```

### Knowledge Base

**Radiotelephony_ATC.json**:

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

### Design Notes

**Current Implementation**: Rule-based keyword matching (not vector RAG)
- ✅ Fast, no external dependencies
- ✅ Sufficient for structured aviation data
- ⚠️ Requires manual rule updates for new patterns

**Runway Direction Disambiguation** (跑道方向标识转换):
- Problem: "跑道两拐左发生鸟击" would be misparsed as position="跑道27" + affected_part="左发"
- Solution: In Stage 1, convert "跑道XX左/右/中" to ICAO format "跑道XXL/R/C"
- Effect: "L" in "跑道27L发生鸟击" no longer conflicts with "左发" regex

**Future Enhancement**: True vector-based RAG
- Requires: embedding model (e.g., sentence-transformers) + vector DB (Chroma/FAISS)
- Pros: Better semantic understanding, automatic pattern learning
- Cons: Additional dependencies, higher latency
- Decision: Defer until rule coverage proves insufficient

### Examples

| Input | Output | Entities |
|-------|--------|----------|
| 川航三幺拐拐 跑道洞两左 报告鸟击 | 川航3U3177 跑道02L 报告鸟击 | {flight_no: "3U3177", position: "02L", event_type: "bird_strike"} |
| 跑道两拐左发生确认鸟击 | 跑道27L发生确认鸟击 | {position: "跑道27L", event_type: "确认鸟击"} |
| 跑道27L发生鸟击 左发受损 | 跑道27L发生鸟击 左发受损 | {position: "跑道27L", affected_part: "左发"} |
| 五洞幺机位发现燃油泄漏 | 501机位发现燃油泄漏 | {position: "501", fluid_type: "FUEL"} |

---

## LLM Configuration

**config/llm_config.py**:
- `LLMClientFactory` supports zhipu (GLM-4) and OpenAI-compatible APIs
- Uses LangChain's `ChatOpenAI` or `ChatZhipuAI`

```python
from config.llm_config import LLMClientFactory

llm = LLMClientFactory.create(
    provider="zhipu",  # or "openai"
    model="glm-4",
    api_key="your_api_key"
)
```

---

## Semantic Understanding Module

### Overview

The semantic understanding module provides **optional LLM-driven entity extraction** with confidence scoring, complementing the default regex-based extraction.

### Configuration

```bash
# .env
ENABLE_SEMANTIC_UNDERSTANDING=true  # Default: false
```

### Implementation

**agent/nodes/semantic_understanding.py**:

When enabled, the input parser uses a **hybrid extraction strategy**:

1. **Semantic Extraction** (LLM-based):
   - `understand_conversation()` → LLM analyzes user input + conversation history
   - Returns entities with confidence scores (0-1 scale)
   - Example output:
     ```python
     {
       "flight_no": {"value": "3U3177", "confidence": 0.95},
       "position": {"value": "501", "confidence": 0.90},
       "fluid_type": {"value": "FUEL", "confidence": 0.85}
     }
     ```

2. **Confidence Splitting**:
   - High confidence (≥0.8): Entities accepted automatically
   - Low confidence (<0.8): Flagged for user clarification

3. **Regex Fallback**:
   - Deterministic `extract_entities()` regex patterns supplement LLM extraction
   - Ensures critical fields (position, flight_no) are never missed

### Workflow

```
Input → RadiotelephonyNormalizer (always on)
      ↓
      If ENABLE_SEMANTIC_UNDERSTANDING:
        → understand_conversation() → LLM extraction
        → split_by_confidence() → High vs Low
        → extract_entities() → Regex supplement
      Else:
        → extract_entities_hybrid() → Regex + minimal LLM
```

### Benefits

- Better handling of ambiguous or colloquial input
- Context-aware extraction using conversation history
- Graceful degradation with confidence scoring

### Trade-offs

- Additional LLM call (adds ~1-2s latency)
- Slightly higher API costs
- May extract false positives with low confidence

### Recommendation

Enable for scenarios with complex natural language input; disable for structured/formulaic input to optimize latency.

---

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

---

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

---

## Production Readiness Checklist

### Must-Have (Blocking Production)

- [ ] **Persistent storage** (PostgreSQL/Redis) for sessions
  - Replace MemorySessionStore with database-backed storage
  - Implement session recovery after restart
  - Add session expiration and cleanup

- [ ] **Docker containerization** with docker-compose
  - Multi-stage Dockerfile for optimized image size
  - docker-compose.yml with all services (app, db, redis)
  - Environment variable management

- [ ] **Structured logging** (JSON format) in all critical paths
  - Replace print statements with logger calls
  - Add request ID tracing
  - Configure log aggregation (e.g., ELK stack)

- [ ] **Health check endpoint** (`/health` with liveness + readiness)
  - Liveness: Is the service running?
  - Readiness: Can the service handle requests?
  - Check dependencies (DB, LLM API)

- [ ] **Basic metrics** (request count, response time, active sessions)
  - Prometheus metrics endpoint
  - Custom business metrics (scenarios processed, tools used)
  - Grafana dashboards

- [ ] **Database for reports** (replace file-based storage)
  - PostgreSQL schema for reports
  - Report versioning and audit trail
  - Efficient querying and indexing

- [ ] **API authentication** (API key or JWT)
  - API key middleware
  - Rate limiting per key
  - Token rotation mechanism

- [ ] **Secrets management** (remove hardcoded API keys)
  - Use environment variables
  - Integrate with secrets manager (AWS Secrets Manager, Vault)
  - Rotate secrets regularly

### Should-Have (High Priority)

- [ ] **Configuration profiles** (dev/staging/prod separation)
  - Separate config files for each environment
  - Override mechanisms (env vars > config files)
  - Validation of required config

- [ ] **Comprehensive error handling** (custom exception hierarchy)
  - Define domain-specific exceptions
  - Consistent error response format
  - Client-friendly error messages

- [ ] **Input validation middleware** (centralized validation)
  - Pydantic models for all API requests
  - Automatic validation error responses
  - Sanitize user inputs

- [ ] **Rate limiting** (per-IP request throttling)
  - Token bucket or sliding window algorithm
  - Different limits for different endpoints
  - 429 responses with retry-after headers

- [ ] **CI/CD pipeline** (GitHub Actions for test + deploy)
  - Automated testing on PR
  - Linting and type checking
  - Automated deployment to staging/prod

- [ ] **Test coverage reporting** (pytest-cov with 80%+ target)
  - Coverage reports in CI
  - Enforce minimum coverage
  - Identify untested code paths

- [ ] **API documentation** (OpenAPI/Swagger specs)
  - Auto-generated from FastAPI
  - Interactive API explorer
  - Code examples in multiple languages

### Nice-to-Have (Enhancement)

- [ ] **Caching layer** (Redis for frequent queries)
  - Cache flight data, weather, topology
  - TTL-based invalidation
  - Cache warming on startup

- [ ] **Message queue** (Celery/RabbitMQ for async processing)
  - Offload long-running tasks
  - Report generation in background
  - Retry mechanism for failed tasks

- [ ] **Distributed tracing** (Jaeger/Datadog integration)
  - Trace requests across services
  - Identify performance bottlenecks
  - Root cause analysis for errors

- [ ] **Custom Prometheus metrics** (business-specific metrics)
  - Scenario completion rates
  - Average handling time per scenario
  - Tool usage statistics

- [ ] **Multi-language support** (i18n for prompts and reports)
  - Language detection from request
  - Translated prompts and responses
  - Locale-specific formatting

- [ ] **Automated rollback** (blue-green deployment)
  - Zero-downtime deployment
  - Health checks before traffic switch
  - Quick rollback on failure

### Current Status: 45% production-ready (Early Beta)

See [Production Readiness Assessment](./docs/PRODUCTION_READINESS.md) for detailed analysis.

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

---

## Additional Resources

For more documentation, see:
- **CLAUDE.md**: High-level overview and quick start
- **docs/API_DOCUMENTATION.md**: API schemas and examples
- **docs/SCENARIO_FIELD_CONTRACTS.md**: Field definitions for each scenario
- **docs/ARCHITECTURE_DECISIONS.md**: Design decisions and trade-offs
- **docs/DEPLOYMENT_GUIDE.md**: Production deployment instructions
- **docs/PRODUCTION_READINESS.md**: Detailed production readiness assessment

## Testing Coverage

Test structure:
```
tests/
├── agent/          # 8 node tests
├── tools/          # Tool-specific unit tests
├── fsm/            # FSM engine tests
├── constraints/    # Constraint checker tests
└── integration/    # End-to-end scenario tests
```

Run full test suite:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=agent --cov=tools --cov=fsm --cov-report=html
```
