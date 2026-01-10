# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Airport emergency response intelligent agent system that combines **ReAct Agent** with **FSM (Finite State Machine) validation** for handling airport apron incidents like fuel spills. The system uses LLM-driven reasoning while ensuring compliance through deterministic validation layers.

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
└── scripts/         # Data processing scripts (offline)
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
- `input_parser.py`: Entity extraction from Chinese text (position, fluid type, engine status). Automatically retrieves flight info from `data/raw/航班计划/Log_*.txt` and performs topology analysis from `scripts/data_processing/topology_clustering_based.json`.
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
- `information/`: `ask_for_detail`, `get_aircraft_info` (automatically called when flight number is detected)
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
