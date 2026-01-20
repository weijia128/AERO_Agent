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
│   └── nodes/       # Graph nodes (8 implementations)
│       ├── input_parser.py        # Entity extraction + auto-enrichment
│       ├── reasoning.py           # ReAct reasoning loop
│       ├── tool_executor.py       # Tool execution
│       ├── fsm_validator.py       # FSM validation
│       ├── output_generator.py    # Report generation
│       ├── semantic_understanding.py  # Optional LLM semantic extraction
│       ├── dialogue_strategy.py   # Dialog state management
│       └── ask_handler.py         # User question handling
├── tools/           # Tool system
│   ├── registry.py  # Tool registration
│   ├── base.py      # BaseTool class
│   ├── information/ # Info query tools (6 tools)
│   ├── spatial/     # Topology analysis tools (5 tools)
│   ├── knowledge/   # RAG knowledge retrieval
│   ├── assessment/  # Risk assessment (3 specialized tools)
│   └── action/      # Action tools (notify, report)
├── fsm/             # Finite State Machine engine
│   ├── engine.py    # FSMEngine core logic
│   ├── validator.py # FSMValidator for state validation
│   ├── states.py    # FSMState enum + transition rules
│   └── transitions.py  # State transition definitions
├── constraints/     # Constraint checking system
│   ├── checker.py   # Rule-based constraint checker
│   └── loader.py    # Dynamic constraint loading
├── scenarios/       # Scenario configurations
│   ├── base.py      # ScenarioRegistry
│   ├── oil_spill/   # Oil spill scenario (complete)
│   └── bird_strike/ # Bird strike scenario (complete)
├── tests/           # Test files (pytest auto-discovery)
│   ├── agent/       # Agent node tests
│   ├── tools/       # Tool tests
│   ├── fsm/         # FSM tests
│   ├── constraints/ # Constraint tests
│   └── integration/ # Integration tests
├── demos/           # Demo scripts
├── docs/            # Documentation and design docs
├── apps/            # Entry points (CLI + API)
│   ├── run_agent.py # CLI interface
│   └── api/         # FastAPI server
├── config/          # Configuration files
├── data/            # Data files
│   ├── raw/         # Raw data (flight plans, weather, ATC rules)
│   ├── processed/   # Processed data (weather CSV/XLSX)
│   └── spatial/     # Spatial data (topology graphs)
├── outputs/         # Generated reports (reports/ final checklists, advice/ comprehensive analysis)
└── scripts/         # Data processing scripts
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

### High-Level Workflow

1. **Input Parser**: Extracts entities from Chinese text using two-stage radiotelephony normalization
   - Stage 1: Basic rule-based conversion (洞→0, 幺→1, 拐→7)
   - Stage 2: LLM + rule-based Few-shot retrieval
   - Auto-enrichment: Parallel queries for flight info, topology, weather
   - Flight plan lookup records `reference_flight` time for downstream impact prediction

2. **Reasoning Node**: ReAct loop with dynamic scenario prompts
   - Uses tools to gather information and take actions
   - Follows scenario-specific field collection order
   - For oil_spill, runs comprehensive analysis after P1 + risk assessment, then asks for supplemental info before final report

3. **Tool Executor**: Executes tools from registry
   - Information tools: ask, get_aircraft_info, flight_plan_lookup, get_weather, smart_ask
   - Spatial tools: topology analysis, impact zone calculation (BFS diffusion)
   - Assessment tools: risk scoring engines (oil spill 12-rule, bird strike BSRC)
   - Action tools: notify departments, generate reports

4. **FSM Validator**: Validates workflow compliance
   - Checks preconditions before state transitions
   - Verifies mandatory actions (e.g., fire dept notification for HIGH risk)
   - Infers current state from AgentState completion

5. **Output Generator**: Creates final incident reports
   - Builds timeline of actions
   - Generates recommendations based on risk level
   - Compiles affected areas and flight impacts
   - Oil spill comprehensive analysis is saved to `outputs/advice` (Markdown + JSON) before final report

## Core Components

### LangGraph State Machine
- Entry point: `input_parser` → `reasoning` → conditional routing
- Key routing: `should_continue()`, `after_tool_execution()`, `after_fsm_validation()`

### Agent State
- `AgentState` TypedDict: incident info, checklist, FSM state, risk assessment, spatial analysis
- `FSMState` enum: INIT → P1_RISK_ASSESS → P2_IMMEDIATE_CONTROL → ... → COMPLETED

### Scenario System
- Each scenario has `prompt.yaml` defining system prompt and field order
- Dynamic prompt loading via `ScenarioRegistry`
- Scenarios: `oil_spill` (complete), `bird_strike` (complete), `tire_burst` (planned)

### Tool System
- **Information tools** (6): Query data from databases and files
- **Spatial tools** (5): Topology analysis using NetworkX graph algorithms
- **Assessment tools** (3): Risk scoring engines (scenario-specific)
- **Action tools** (2): External notifications and report generation

Flight impact prediction uses `reference_flight.reference_time` when available and logs the prediction base time in its observation output.

### FSM System
9-state workflow validation:
```
INIT → P1_RISK_ASSESS → P2_IMMEDIATE_CONTROL → P3_IMPACT_ANALYSIS →
P4_NOTIFICATION → P5_MONITORING → P6_FOLLOWUP → P7_REPORTING → P8_CLOSE → COMPLETED
```

## Supported Scenarios

- **oil_spill** (implemented): Fuel/hydraulic/oil leak handling
  - 12-rule risk assessment engine
  - BFS graph diffusion for impact zones
  - Mandatory fire dept notification for HIGH risk

- **bird_strike** (implemented): Bird strike incident handling
  - BSRC weighted scoring engine
  - Phase-based risk assessment
  - Evidence strength evaluation

- **tire_burst**, **runway_incursion** (planned)

### Adding New Scenarios
1. Create `scenarios/<name>/` with `prompt.yaml`, `checklist.yaml`, `config.yaml`
2. Register in `scenarios/base.py`
3. Add scenario-specific tools and rules

See `scenarios/SCENARIO_GUIDE.md` and `CLAUDE_DEV.md` for detailed instructions.

## API Endpoints

- `POST /event/start`: Start new incident session
- `POST /event/chat`: Continue conversation in session
- `GET /event/{session_id}`: Get session status
- `GET /event/{session_id}/report`: Get generated report
- `DELETE /event/{session_id}`: Close session

See [API Documentation](./docs/API_DOCUMENTATION.md) for schemas and examples.

## Configuration Flags

```bash
# .env configuration
ENABLE_SEMANTIC_UNDERSTANDING=false  # Enable LLM semantic extraction
LLM_PROVIDER=zhipu                   # or "openai"
LLM_MODEL=glm-4                      # Model name
LLM_API_KEY=your_key_here            # API key

# Agent behavior
MAX_ENRICHMENT_WORKERS=3             # Parallel enrichment threads
ENRICHMENT_TIMEOUT=10                # Seconds per enrichment future
```

## Troubleshooting Guide

### Common Issues

**Issue: "Tool not found: xyz"**
- **Cause**: Tool not registered in ToolRegistry
- **Solution**: Check `tools/registry.py` registration

**Issue: Session data lost after restart**
- **Cause**: Using MemorySessionStore (in-memory only)
- **Solution**: Implement PostgreSQL session store

**Issue: FSM validation errors block progress**
- **Cause**: Mandatory actions not completed
- **Solution**: Check `validation_result.errors`, complete required actions

**Issue: Spatial analysis returns empty impact zone**
- **Cause**: Position not found in topology graph
- **Solution**: Verify position in `scripts/data_processing/topology_clustering_based.json`

### Debugging Tips

**Enable verbose logging:**
```bash
LOG_LEVEL=DEBUG  # In .env
```

**Enable LangSmith tracing:**
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=aero-agent-dev
```

**Test individual tools:**
```bash
pytest tests/tools/test_assess_risk.py -v -s
```

## Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| Oil spill scenario | ✅ Complete | Full FSM + 12-rule engine |
| Bird strike scenario | ✅ Complete | BSRC scoring engine |
| Tire burst scenario | 📋 Planned | Template ready |
| Flight impact prediction | ✅ Complete | Dynamic time window from flight number |
| Report template engine | ⚠️ String concat | Needs refactoring |
| Session persistence | ⚠️ Memory only | Needs PostgreSQL/Redis |

## Production Readiness

Current Status: **45% production-ready** (Early Beta)

### Must-Have Before Production
- [ ] Persistent storage (PostgreSQL/Redis)
- [ ] Docker containerization
- [ ] Structured logging (JSON format)
- [ ] Health check endpoint
- [ ] API authentication
- [ ] Secrets management

See [Production Readiness Assessment](./docs/PRODUCTION_READINESS.md) for full checklist.

## Further Documentation

For detailed technical documentation, see:
- **CLAUDE_DEV.md**: Detailed data flows, tool development guide, code quality guidelines
- **docs/API_DOCUMENTATION.md**: API schemas and examples
- **docs/SCENARIO_FIELD_CONTRACTS.md**: Field definitions for each scenario
- **docs/ARCHITECTURE_DECISIONS.md**: Design decisions and trade-offs
- **docs/DEPLOYMENT_GUIDE.md**: Production deployment instructions
- **docs/DYNAMIC_TIME_WINDOW.md**: Flight-based dynamic time window feature (v2.0.0)

## Recent Updates

### v2.0.0 (2026-01-20) - Dynamic Time Window Feature

**Major Improvement: Flight-Based Time Window Prediction**

Replaced hardcoded incident time with dynamic time window calculation based on user-provided flight numbers:

- ✅ **flight_plan_lookup** enhanced to extract flight time and record `reference_flight` in state
- ✅ **predict_flight_impact** now uses 3-tier time source priority:
  1. `reference_flight.reference_time` (from flight number query)
  2. `incident.incident_time` (user-specified time)
  3. Default fallback: `2026-01-06 10:00:00`
- ✅ **analyze_spill_comprehensive** reports display reference flight and time source
- ✅ Time window: `reference_time` + (cleanup_time + 30min buffer)

**Example workflow:**
```
User: "CES2876航班在501机位漏油"
→ System queries CES2876 → finds takeoff at 08:35
→ Analysis window: 08:35 - 10:05 (based on actual flight time)
→ Predicts impact on 12 adjacent flights in that window
```

**Test coverage:** `tests/test_dynamic_time_window.py` (4 scenarios, all passing)

**Documentation:** See `docs/DYNAMIC_TIME_WINDOW.md` for complete technical details

---

### v1.0.0 (2026-01-15)

**Newly Documented Modules**
- Semantic Understanding Module with confidence scoring
- Dialogue Strategy Manager for conversation flow
- Smart Ask Tool for multi-field questioning
- Complete FSM Engine with precondition checking
- Constraint System with dynamic rule evaluation

**Architectural Clarifications**
- `assess_risk.py` is a compatibility shim
- Actual implementations: `assess_oil_spill_risk.py`, `assess_bird_strike_risk.py`
- Primary topology: `scripts/data_processing/topology_clustering_based.json`
- Weather formats: CSV and XLSX both supported

**Data Files**
- `awos_weather_2026-01-13.csv` / `.xlsx` - Weather observations
- `topology_clustering_based.json` - Airport topology graph
- `Radiotelephony_ATC.json` - ATC normalization rules
- `BSRC.json` - Bird strike risk classification

Documentation accuracy: **98%**
