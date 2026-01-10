# 项目重构改进计划

## P0 高优先级改进（建议2周内完成）

### 1. 使用Jinja2模板替代字符串拼接 ⚠️

**问题：** `agent/nodes/output_generator.py` (778行) 全部是字符串拼接

**解决方案：**
```bash
# 安装依赖
pip install jinja2

# 创建模板目录
mkdir -p agent/templates
```

**示例实现：**
```python
# agent/templates/report_template.md.j2
# 机坪应急响应检查单

## 1. 事件摘要
- 时间: {{ incident.report_time }}
- 位置: {{ incident.position }}
- 航班号: {{ incident.flight_no }}
- 油液类型: {{ incident.fluid_type }}

## 2. 风险评估
- 风险等级: {{ risk.level }}
- 风险分数: {{ risk.score }}
- 风险因素: {{ risk.factors | join(', ') }}

## 3. 处置措施
{% for action in actions_taken %}
- [{{ action.timestamp }}] {{ action.action }}: {{ action.result }}
{% endfor %}

## 4. 影响范围
{% if spatial.affected_runways %}
受影响跑道: {{ spatial.affected_runways | join(', ') }}
{% endif %}
```

```python
# agent/nodes/output_generator.py (重构后)
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# 初始化Jinja2环境
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def generate_output_node(state: AgentState) -> AgentState:
    """生成最终报告（使用模板）"""
    template = jinja_env.get_template("report_template.md.j2")

    report = template.render(
        incident=state.get("incident", {}),
        risk=state.get("risk_assessment", {}),
        spatial=state.get("spatial_analysis", {}),
        actions_taken=state.get("actions_taken", []),
        notifications=state.get("notifications_sent", []),
    )

    state["final_report"] = report
    return state
```

**收益：**
- 代码从778行减少到~50行 (90%+减少)
- 模板可视化，非技术人员也能调整格式
- 支持多语言报告（i18n）

---

### 2. 拆分长函数 ⚠️

**问题：** 多个文件存在400+行长函数

**需要拆分的文件：**
```python
# reasoning.py: build_scenario_prompt() ~200行
# input_parser.py: input_parser_node() ~495行
# scripts/data_processing/build_topology_from_clustering.py: ~406行
```

**重构示例 - reasoning.py:**
```python
# 原代码：build_scenario_prompt() 200+行
def build_scenario_prompt(state, scenario, tools_desc):
    prompt = ""
    # ... 200行混合逻辑
    return prompt

# 重构后：拆分为小函数
def build_scenario_prompt(state, scenario, tools_desc):
    """构建场景专属提示（主函数）"""
    sections = [
        _build_system_prompt(scenario),
        _build_tools_section(tools_desc),
        _build_context_summary(state),
        _build_checklist_section(state, scenario),
        _build_fsm_section(state),
        _build_constraints_section(state),
        _build_examples_section(scenario),
    ]
    return "\n\n".join(sections)

def _build_system_prompt(scenario) -> str:
    """构建系统提示"""
    return scenario.prompt_config.get("system_prompt", "")

def _build_context_summary(state) -> str:
    """构建上下文摘要"""
    incident = state.get("incident", {})
    summary_parts = []

    if incident.get("fluid_type"):
        summary_parts.append(f"油液类型: {incident['fluid_type']}")
    if incident.get("position"):
        summary_parts.append(f"位置: {incident['position']}")
    # ...

    return "## 当前事件状态\n" + "\n".join(summary_parts)

def _build_checklist_section(state, scenario) -> str:
    """构建Checklist状态"""
    checklist = state.get("checklist", {})
    field_order = scenario.prompt_config.get("field_order", [])

    pending = [f for f in field_order if not checklist.get(f, False)]

    if not pending:
        return "## Checklist状态\n所有必要信息已收集完毕 ✓"

    return f"## Checklist状态\n待收集信息: {', '.join(pending)}"

# 其他辅助函数...
```

**收益：**
- 每个函数职责单一，易于测试
- 代码可读性大幅提升
- 便于复用（如_build_context_summary可在多处使用）

---

### 3. 统一状态管理（TypedDict → Pydantic） ⚠️

**问题：** `agent/state.py` 中TypedDict和Pydantic混用

```python
# 当前问题
class AgentState(TypedDict, total=False):  # TypedDict
    incident: Dict[str, Any]  # 实际是IncidentInfo (Pydantic)
    risk_assessment: Dict[str, Any]  # 实际是RiskAssessment (Pydantic)
    # 类型安全性差，IDE无法提示
```

**解决方案：全部使用Pydantic BaseModel**

```python
# agent/state.py (重构后)
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class AgentState(BaseModel):
    """Agent 状态（统一使用Pydantic）"""

    # ===== 基础信息 =====
    session_id: str
    scenario_type: str = "oil_spill"
    created_at: datetime = Field(default_factory=datetime.now)

    # ===== 事件信息（直接使用Pydantic模型）=====
    incident: IncidentInfo = Field(default_factory=IncidentInfo)

    # ===== 对话历史 =====
    messages: List[Dict[str, str]] = Field(default_factory=list)

    # ===== ReAct 推理 =====
    reasoning_steps: List[ReasoningStep] = Field(default_factory=list)
    current_thought: str = ""
    current_action: Optional[str] = None
    current_action_input: Dict[str, Any] = Field(default_factory=dict)

    # ===== 分析结果（直接使用Pydantic模型）=====
    risk_assessment: Optional[RiskAssessment] = None
    spatial_analysis: Optional[SpatialAnalysis] = None

    # ===== Checklist =====
    checklist: Dict[str, bool] = Field(default_factory=dict)

    # ===== FSM 状态 =====
    fsm_state: FSMState = FSMState.INIT
    fsm_history: List[FSMTransition] = Field(default_factory=list)

    # ===== 约束状态 =====
    mandatory_actions_done: Dict[str, bool] = Field(default_factory=dict)

    # ===== 执行记录 =====
    actions_taken: List[ActionRecord] = Field(default_factory=list)
    notifications_sent: List[Dict[str, Any]] = Field(default_factory=list)

    # ===== 控制状态 =====
    iteration_count: int = 0
    is_complete: bool = False
    awaiting_user: bool = False
    error: str = ""

    # ===== 最终输出 =====
    final_report: Optional[FinalReport] = None
    final_answer: str = ""

    class Config:
        arbitrary_types_allowed = True  # 允许自定义类型
        validate_assignment = True  # 赋值时验证
```

**LangGraph兼容性处理：**
```python
# agent/graph.py (如果LangGraph要求TypedDict)
from typing import TypedDict

class LangGraphState(TypedDict):
    """LangGraph适配层"""
    state_data: str  # 序列化的AgentState

def pydantic_to_langgraph(state: AgentState) -> LangGraphState:
    return {"state_data": state.model_dump_json()}

def langgraph_to_pydantic(lg_state: LangGraphState) -> AgentState:
    return AgentState.model_validate_json(lg_state["state_data"])
```

**收益：**
- 完整的类型检查和IDE支持
- 自动验证（如枚举值、必填字段）
- 清晰的数据结构文档

---

### 4. 规则外部化配置 ⚠️

**问题：** 风险评估规则硬编码在 `assess_risk.py`

```python
# 当前问题
RISK_RULES = [
    {
        "conditions": {"fluid_type": "FUEL", "continuous": True, "engine_status": "RUNNING"},
        "level": "HIGH",
        "score": 95,
        "description": "航空燃油+持续泄漏+发动机运转=极高火灾风险",
    },
    # ... 12条规则硬编码
]
```

**解决方案：移到YAML配置**

```yaml
# scenarios/oil_spill/risk_rules.yaml
rules:
  - id: FUEL_RUNNING_CONTINUOUS
    priority: 1  # 优先级越低越优先匹配
    conditions:
      fluid_type: FUEL
      continuous: true
      engine_status: RUNNING
    result:
      level: HIGH
      score: 95
      description: 航空燃油+持续泄漏+发动机运转=极高火灾风险(易燃易爆)
    immediate_actions:
      - action: notify_department
        params:
          department: 消防
          priority: immediate
      - action: request_engine_shutdown
      - action: evacuate_area
        params:
          radius_meters: 100

  - id: FUEL_RUNNING
    priority: 2
    conditions:
      fluid_type: FUEL
      engine_status: RUNNING
    result:
      level: HIGH
      score: 90
      description: 航空燃油+发动机运转=高火灾风险(禁止任何火花)
    immediate_actions:
      - action: notify_department
        params:
          department: 消防
          priority: immediate
      - action: request_engine_shutdown

  # ... 其他规则

# 扩散规则
spatial_rules:
  - fluid_type: FUEL
    risk_level: HIGH
    bfs_radius: 3
    impact_runway: true

  - fluid_type: FUEL
    risk_level: MEDIUM
    bfs_radius: 2
    impact_runway: true

  - fluid_type: HYDRAULIC
    risk_level: [HIGH, MEDIUM_HIGH]
    bfs_radius: 2
    impact_runway: false
```

```python
# tools/assessment/assess_risk.py (重构后)
import yaml
from pathlib import Path
from typing import List, Dict, Any

class RuleEngine:
    """规则引擎"""

    def __init__(self, rules_file: str):
        self.rules = self._load_rules(rules_file)

    def _load_rules(self, rules_file: str) -> List[Dict]:
        """从YAML加载规则"""
        with open(rules_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        # 按priority排序
        rules = sorted(config['rules'], key=lambda r: r['priority'])
        return rules

    def match(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """匹配规则"""
        for rule in self.rules:
            if self._check_conditions(incident, rule['conditions']):
                return rule['result']

        # 默认规则
        return {
            "level": "LOW",
            "score": 10,
            "description": "未匹配到高风险规则",
        }

    def _check_conditions(self, incident: Dict, conditions: Dict) -> bool:
        """检查条件是否满足"""
        for key, expected in conditions.items():
            actual = incident.get(key)
            if actual is None or actual != expected:
                return False
        return True

class AssessRiskTool(BaseTool):
    """风险评估工具"""

    name = "assess_risk"
    description = "基于规则引擎评估漏油事件的风险等级"

    def __init__(self, scenario_type: str = "oil_spill"):
        rules_file = f"scenarios/{scenario_type}/risk_rules.yaml"
        self.engine = RuleEngine(rules_file)

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        incident = state.get("incident", {}).copy()
        incident.update(inputs)

        result = self.engine.match(incident)

        return {
            "observation": f"风险评估完成: 等级={result['level']}, 分数={result['score']}",
            "risk_assessment": result,
            "mandatory_actions_done": {"risk_assessed": True},
        }
```

**收益：**
- 规则可视化，业务人员可直接修改
- 支持场景专属规则（不同机场不同规则）
- 规则版本管理（Git追踪变更）
- 易于A/B测试不同规则

---

### 5. 增强错误处理和重试机制 ⚠️

**问题：** LLM调用失败处理简单，无重试

```python
# 当前问题
try:
    response = llm.invoke(prompt)
except Exception as e:
    return {"error": str(e)}  # 仅返回错误，无重试
```

**解决方案：使用tenacity库实现智能重试**

```python
# config/llm_config.py (重构后)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import logging

logger = logging.getLogger(__name__)

class RobustLLMClient:
    """带重试和降级的LLM客户端"""

    def __init__(self, provider: str, model: str, api_key: str):
        self.client = self._create_client(provider, model, api_key)
        self.fallback_model = "glm-4-flash"  # 快速备用模型

    @retry(
        stop=stop_after_attempt(3),  # 最多重试3次
        wait=wait_exponential(multiplier=1, min=2, max=10),  # 指数退避
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    def invoke(self, prompt: str, **kwargs) -> str:
        """调用LLM（带重试）"""
        try:
            logger.info(f"调用LLM: {self.client.model_name}")
            response = self.client.invoke(prompt, **kwargs)
            return response.content

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            # 尝试降级到快速模型
            if self.fallback_model and self.client.model_name != self.fallback_model:
                logger.warning(f"降级到备用模型: {self.fallback_model}")
                return self._invoke_fallback(prompt, **kwargs)
            raise

    def _invoke_fallback(self, prompt: str, **kwargs) -> str:
        """使用备用模型"""
        fallback_client = self._create_client(
            self.client.provider,
            self.fallback_model,
            self.client.api_key
        )
        response = fallback_client.invoke(prompt, **kwargs)
        return response.content
```

**节点级错误处理：**
```python
# agent/nodes/reasoning.py
def reasoning_node(state: AgentState) -> AgentState:
    """推理节点（增强错误处理）"""
    try:
        llm = get_llm_client()
        response = llm.invoke(prompt)
        # 正常处理...

    except Exception as e:
        logger.error(f"推理失败: {e}", exc_info=True)

        # 保存错误上下文
        state["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "node": "reasoning",
            "timestamp": datetime.now().isoformat(),
        }

        # 尝试恢复策略
        if state.get("iteration_count", 0) < 3:
            # 重试：简化prompt
            state["current_thought"] = "系统遇到临时问题，正在重试..."
            return state
        else:
            # 降级：切换到规则模式
            state["final_answer"] = "系统遇到问题，已切换到规则模式处理"
            state["is_complete"] = True
            return state
```

**收益：**
- 提高系统稳定性
- 透明的错误追踪
- 优雅降级，不影响用户体验

---

## P1 中优先级改进（建议1个月内完成）

### 6. 合并场景配置文件 ⚠️

**问题：** 每个场景需要4个YAML文件（config.yaml, checklist.yaml, fsm_states.yaml, prompt.yaml）

**解决方案：合并为单个scenario.yaml**

```yaml
# scenarios/oil_spill/scenario.yaml
metadata:
  id: oil_spill
  name: 燃油泄漏
  version: "1.0.0"
  description: 机场机坪燃油/液压油/滑油泄漏应急响应

# Prompt配置
prompt:
  system_prompt: |
    你是机场机坪应急响应专家 Agent，专门处理漏油事件...

  field_order:
    - flight_no
    - position
    - fluid_type
    - engine_status
    - continuous
    - leak_size

  field_names:
    flight_no: 航班号
    position: 事发位置
    fluid_type: 油液类型
    engine_status: 发动机状态
    continuous: 持续状态
    leak_size: 泄漏面积

  ask_prompts:
    flight_no: "请提供涉事飞机的航班号？"
    position: "请报告事件发生的具体位置（机位号或滑行道名称）？"
    # ...

# Checklist配置
checklist:
  p1_fields:
    - key: fluid_type
      type: enum
      options: [FUEL, HYDRAULIC, OIL]
      required: true
      ask_prompt: "请确认泄漏的油液类型：燃油/液压油/滑油？"

    - key: position
      type: airport_node
      required: true
      ask_prompt: "请报告事件发生的具体位置（机位号或滑行道名称）？"

    # ...

  p2_fields:
    - key: leak_size
      type: enum
      options: [SMALL, MEDIUM, LARGE]
      # ...

# FSM状态配置
fsm_states:
  - id: INIT
    name: 初始状态
    description: 事件刚报告，开始信息收集

  - id: P1_RISK_ASSESS
    name: 风险评估
    preconditions:
      - checklist.p1_complete
    triggers:
      - tool: assess_risk
    description: 完成P1信息收集后，进行风险评估

  # ...

# 强制动作触发规则
mandatory_triggers:
  - condition:
      risk_level: HIGH
    actions:
      - action: notify_department
        params:
          department: 消防
          priority: immediate
        error_if_not_done: true

  # ...

# 风险评估规则（内联或引用）
risk_rules: !include risk_rules.yaml

# 空间分析配置
spatial_config:
  topology_file: scripts/data_processing/topology_clustering_based.json
  diffusion_rules: !include spatial_rules.yaml

# 报告模板
report_template: report_template.md.j2
```

```python
# scenarios/base.py (重构后)
import yaml

class ScenarioConfig(BaseModel):
    """统一的场景配置"""
    metadata: Dict[str, Any]
    prompt: Dict[str, Any]
    checklist: Dict[str, Any]
    fsm_states: List[Dict[str, Any]]
    mandatory_triggers: List[Dict[str, Any]]
    risk_rules: Dict[str, Any]  # 可以是内联或引用
    spatial_config: Dict[str, Any]
    report_template: str

    @classmethod
    def from_file(cls, scenario_dir: str) -> "ScenarioConfig":
        """从YAML加载配置（支持!include）"""
        config_file = Path(scenario_dir) / "scenario.yaml"

        # 使用自定义YAML加载器支持!include
        def include_constructor(loader, node):
            filepath = Path(scenario_dir) / loader.construct_scalar(node)
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)

        yaml.add_constructor('!include', include_constructor)

        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)

        return cls(**data)
```

**收益：**
- 配置集中管理，易于理解
- 支持模块化（!include引用外部文件）
- 减少配置冗余

---

### 7. 改进会话存储（内存 → Redis/数据库） ⚠️

**问题：** `apps/api/main.py` 使用内存字典存储会话，服务重启丢失

```python
# 当前问题
SESSIONS: Dict[str, AgentState] = {}  # 内存存储，不持久化
```

**解决方案：使用Redis + 可选的数据库持久化**

```python
# api/session_store.py (新建)
from abc import ABC, abstractmethod
import redis
import json
from typing import Optional
from agent.state import AgentState

class SessionStore(ABC):
    """会话存储抽象接口"""

    @abstractmethod
    def save(self, session_id: str, state: AgentState) -> None:
        pass

    @abstractmethod
    def load(self, session_id: str) -> Optional[AgentState]:
        pass

    @abstractmethod
    def delete(self, session_id: str) -> None:
        pass

class RedisSessionStore(SessionStore):
    """Redis会话存储"""

    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        self.client = redis.from_url(redis_url)
        self.ttl = ttl  # 会话过期时间（秒）

    def save(self, session_id: str, state: AgentState) -> None:
        key = f"session:{session_id}"
        # Pydantic模型序列化
        data = state.model_dump_json()
        self.client.setex(key, self.ttl, data)

    def load(self, session_id: str) -> Optional[AgentState]:
        key = f"session:{session_id}"
        data = self.client.get(key)
        if not data:
            return None
        return AgentState.model_validate_json(data)

    def delete(self, session_id: str) -> None:
        key = f"session:{session_id}"
        self.client.delete(key)

class DatabaseSessionStore(SessionStore):
    """数据库会话存储（持久化）"""

    def __init__(self, db_url: str):
        from sqlalchemy import create_engine, Column, String, Text, DateTime
        from sqlalchemy.orm import sessionmaker, declarative_base

        Base = declarative_base()

        class Session(Base):
            __tablename__ = 'agent_sessions'

            session_id = Column(String(64), primary_key=True)
            state_data = Column(Text)  # JSON
            created_at = Column(DateTime)
            updated_at = Column(DateTime)

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        self.SessionLocal = sessionmaker(bind=engine)
        self.Session = Session

    def save(self, session_id: str, state: AgentState) -> None:
        db = self.SessionLocal()
        try:
            session = db.query(self.Session).filter_by(session_id=session_id).first()
            data = state.model_dump_json()

            if session:
                session.state_data = data
                session.updated_at = datetime.now()
            else:
                session = self.Session(
                    session_id=session_id,
                    state_data=data,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                db.add(session)

            db.commit()
        finally:
            db.close()

    def load(self, session_id: str) -> Optional[AgentState]:
        db = self.SessionLocal()
        try:
            session = db.query(self.Session).filter_by(session_id=session_id).first()
            if not session:
                return None
            return AgentState.model_validate_json(session.state_data)
        finally:
            db.close()
```

```python
# apps/api/main.py (重构后)
from apps.api.session_store import RedisSessionStore, DatabaseSessionStore
from config.settings import get_settings

settings = get_settings()

# 根据配置选择存储后端
if settings.session_store == "redis":
    session_store = RedisSessionStore(settings.redis_url)
elif settings.session_store == "database":
    session_store = DatabaseSessionStore(settings.database_url)
else:
    session_store = MemorySessionStore()  # 开发环境

@app.post("/event/start")
def start_event(request: StartEventRequest):
    session_id = str(uuid.uuid4())
    state = create_initial_state(session_id, request.scenario_type, request.message)

    # 使用统一接口
    session_store.save(session_id, state)

    return {"session_id": session_id, "status": "started"}

@app.post("/event/chat")
def chat_event(request: ChatEventRequest):
    # 从存储加载
    state = session_store.load(request.session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    # 处理...

    # 保存更新
    session_store.save(request.session_id, state)

    return response
```

**收益：**
- 会话持久化，服务重启不丢失
- 支持水平扩展（多实例共享Redis）
- 灵活的存储策略

---

### 8. 统一Prompt管理 ⚠️

**问题：** LLM提取prompt内嵌在 `input_parser.py` 代码中

```python
# 当前问题
prompt = f"""
你是机场应急响应系统。请从以下文本中提取关键信息：
{user_message}

请提取：
1. 位置
2. 油液类型
...
"""  # 硬编码在代码中
```

**解决方案：所有prompt统一管理**

```
agent/prompts/
├── system/
│   ├── entity_extraction.yaml
│   ├── react_reasoning.yaml
│   └── report_generation.yaml
├── scenarios/
│   ├── oil_spill.yaml
│   ├── bird_strike.yaml
│   └── ...
└── loader.py
```

```yaml
# agent/prompts/system/entity_extraction.yaml
name: entity_extraction
description: 从用户输入中提取事件信息
version: "1.0.0"

prompt_template: |
  你是机场应急响应系统的信息提取模块。

  ## 任务
  从以下用户报告中提取关键信息：

  ```
  {{ user_message }}
  ```

  ## 提取字段
  {% for field in extract_fields %}
  - {{ field.name }}: {{ field.description }}
    {% if field.type == "enum" %}
    可选值: {{ field.options | join(', ') }}
    {% endif %}
  {% endfor %}

  ## 输出格式
  请以JSON格式返回：
  ```json
  {
    {% for field in extract_fields %}
    "{{ field.key }}": <提取值或null>,
    {% endfor %}
  }
  ```

  ## 注意事项
  - 如果信息不明确，返回null
  - 航班号统一转换为ICAO格式（如CA1234 → CCA1234）
  - 位置使用机位号（如501机位）或滑行道名称

examples:
  - input: "501机位，发现燃油泄漏，发动机运转中"
    output:
      position: "501机位"
      fluid_type: "FUEL"
      engine_status: "RUNNING"
      continuous: null
```

```python
# agent/prompts/loader.py (新建)
import yaml
from jinja2 import Template
from pathlib import Path
from typing import Dict, Any

class PromptManager:
    """Prompt管理器"""

    def __init__(self, prompts_dir: str = "agent/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._cache = {}

    def load(self, prompt_name: str, category: str = "system") -> Dict[str, Any]:
        """加载prompt配置"""
        cache_key = f"{category}/{prompt_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt_file = self.prompts_dir / category / f"{prompt_name}.yaml"
        with open(prompt_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self._cache[cache_key] = config
        return config

    def render(self, prompt_name: str, variables: Dict[str, Any], category: str = "system") -> str:
        """渲染prompt模板"""
        config = self.load(prompt_name, category)
        template = Template(config['prompt_template'])
        return template.render(**variables)

# 使用示例
prompt_manager = PromptManager()

def input_parser_node(state: AgentState) -> AgentState:
    user_message = state["messages"][-1]["content"]

    # 加载并渲染prompt
    prompt = prompt_manager.render(
        "entity_extraction",
        variables={
            "user_message": user_message,
            "extract_fields": [
                {"key": "position", "name": "位置", "description": "事发机位或滑行道"},
                {"key": "fluid_type", "name": "油液类型", "type": "enum", "options": ["燃油", "液压油", "滑油"]},
                # ...
            ]
        }
    )

    llm = get_llm_client()
    response = llm.invoke(prompt)
    # ...
```

**收益：**
- Prompt版本管理
- 支持A/B测试不同prompt
- 非技术人员也能调优prompt

---

## P2 低优先级改进（长期优化）

### 9. 数据处理管道模块化

**问题：** `scripts/data_processing/` 中多个文件400+行，流程分散

**建议：**
```python
# scripts/data_processing/pipeline.py (新建)
from abc import ABC, abstractmethod

class PipelineStep(ABC):
    @abstractmethod
    def execute(self, input_data):
        pass

class TrajectoryParsingStep(PipelineStep):
    def execute(self, raw_data):
        # 解析轨迹...
        return parsed_trajectories

class ClusteringStep(PipelineStep):
    def execute(self, trajectories):
        # DBSCAN聚类...
        return clusters

class TopologyBuildingStep(PipelineStep):
    def execute(self, clusters):
        # 构建拓扑图...
        return topology_graph

class TopologyPipeline:
    """拓扑生成管道"""

    def __init__(self):
        self.steps = [
            TrajectoryParsingStep(),
            ClusteringStep(),
            TopologyBuildingStep(),
        ]

    def run(self, input_data):
        data = input_data
        for step in self.steps:
            data = step.execute(data)
        return data
```

---

### 10. 增加集成测试

**建议：**
```python
# tests/test_e2e.py (新建)
import pytest
from apps.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_full_workflow():
    """测试完整工作流"""
    # 1. 启动事件
    response = client.post("/event/start", json={
        "message": "501机位，发现燃油泄漏，发动机运转中，持续滴漏",
        "scenario_type": "oil_spill"
    })
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 继续对话
    response = client.post("/event/chat", json={
        "session_id": session_id,
        "message": "泄漏面积约2平方米"
    })
    assert response.status_code == 200

    # 3. 获取报告
    response = client.get(f"/event/{session_id}/report")
    assert response.status_code == 200
    report = response.json()
    assert report["risk_level"] == "HIGH"
    assert "消防" in report["notifications"]
```

---

## 三、重构实施建议

### 阶段1：基础重构（Week 1-2）
1. ✅ 使用Jinja2模板替代output_generator字符串拼接
2. ✅ 拆分reasoning.py的build_scenario_prompt函数
3. ✅ 规则外部化（risk_rules.yaml）

### 阶段2：架构优化（Week 3-4）
4. ✅ 统一状态管理（TypedDict → Pydantic）
5. ✅ 增强错误处理和重试机制
6. ✅ 合并场景配置文件

### 阶段3：工程化提升（Week 5-6）
7. ✅ 改进会话存储（Redis/数据库）
8. ✅ 统一Prompt管理
9. ✅ 增加集成测试

### 阶段4：长期优化（Week 7+）
10. ✅ 数据处理管道模块化
11. ✅ 性能优化（缓存、并行）
12. ✅ 文档完善

---

## 四、预期收益

### 代码质量提升
- **代码行数减少：** 预计减少30%（主要来自模板化和函数拆分）
- **可读性：** 从6分提升到8分
- **可维护性：** 从6分提升到8分

### 开发效率提升
- **新场景开发：** 从2天降低到0.5天（配置驱动）
- **规则调优：** 从修改代码降低到修改YAML（非技术人员可参与）
- **Bug修复：** 更容易定位问题（模块化、错误追踪）

### 系统稳定性提升
- **LLM调用成功率：** 从90%提升到98%（重试+降级）
- **会话丢失率：** 从100%（重启必丢）降低到0%（持久化）

---

## 五、风险评估

### 重构风险
- **回归风险：** 中等（建议增加测试覆盖率到80%+）
- **兼容性风险：** 低（主要是内部重构，API保持兼容）
- **性能风险：** 低（Pydantic验证有小幅开销，但可接受）

### 缓解措施
1. **渐进式重构：** 按阶段实施，每阶段充分测试
2. **保留备份：** 使用Git分支管理，保留原始代码
3. **灰度发布：** 先在测试环境验证，再上线生产
4. **监控指标：** 追踪响应时间、错误率、会话成功率

---

## 六、参考资料

### 推荐工具
- **Jinja2：** https://jinja.palletsprojects.com/
- **Pydantic：** https://docs.pydantic.dev/
- **Tenacity：** https://tenacity.readthedocs.io/
- **Redis：** https://redis.io/

### 设计模式
- **规则引擎模式：** Martin Fowler's DSL
- **策略模式：** 场景配置驱动
- **模板方法模式：** Pipeline设计

---

**总结：** 这是一个架构优秀但工程化不足的项目。通过系统的重构，可以将其打造为工业级的应急响应Agent框架，适用于机场、港口、工厂等多种应急场景。
