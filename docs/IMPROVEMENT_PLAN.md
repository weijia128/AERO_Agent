# AERO_Agent 项目优化计划

**创建日期**: 2026-01-20
**当前生产就绪度**: 45%
**目标生产就绪度**: 75%+

---

## 执行摘要

本计划基于项目全面评估，将优化任务分为4个阶段，预计8周完成。每个任务包含具体的执行步骤、涉及文件、验收标准和预估工时。

---

## 进度更新

**更新日期**: 2026-01-21

- Phase 1.4 输入验证：对齐工具 input schema 与实际入参，补齐兼容字段映射，修正报告格式映射与中文航班号校验
- Phase 1.4 测试：补充/更新输入验证单元测试与真实工具 alias 集成用例
- Phase 1.3 认证依赖：补充 `python-jose` 依赖声明
- Phase 1.1/1.2 日志：补齐 FSM fallback 异常日志
- 已验证：
  - `pytest tests/tools/test_input_validation.py -v` 通过（58 passed）
  - `pytest tests/api/test_auth.py -v` 通过（18 passed）
- 待确认：执行检查清单剩余项需逐项验证

---

## Phase 1: 紧急修复（第 1-2 周）

### 1.1 修复异常处理 [P0-关键]

**问题**: 多处使用裸露 `except:` 语句，静默吞掉异常

**涉及文件**:
| 文件 | 问题行数 | 严重程度 |
|------|----------|----------|
| `tools/spatial/predict_flight_impact.py` | L88-94, L226-227 | 高 |
| `tools/assessment/analyze_spill_comprehensive.py` | L772, L852 | 高 |
| `scripts/data_processing/parse_flight_plan.py` | 多处 | 中 |
| `agent/nodes/input_parser.py` | L150+ | 中 |

**执行步骤**:

```bash
# Step 1: 查找所有裸露的 except 语句
grep -rn "except:" --include="*.py" | grep -v "except.*:"

# Step 2: 逐个修复
```

**修复模板**:
```python
# 修复前
try:
    result = some_operation()
except:
    pass

# 修复后
import logging
logger = logging.getLogger(__name__)

try:
    result = some_operation()
except FileNotFoundError as e:
    logger.error(f"文件未找到: {e}", exc_info=True)
    return {"observation": f"文件未找到: {str(e)}", "error": True}
except ValueError as e:
    logger.warning(f"值错误: {e}")
    return {"observation": f"参数无效: {str(e)}", "error": True}
except Exception as e:
    logger.exception(f"未预期的错误: {type(e).__name__}")
    raise  # 或返回错误信息
```

**验收标准**:
- [ ] `grep -rn "except:" --include="*.py" | grep -v "except.*:"` 返回空
- [ ] 所有异常都有日志记录
- [ ] 测试通过率不下降

**预估工时**: 4小时

---

### 1.2 添加结构化日志 [P0-关键]

**问题**: Agent 节点缺少日志记录，无法调试和监控

**涉及文件**:
| 文件 | 需要添加日志的位置 |
|------|-------------------|
| `agent/nodes/tool_executor.py` | 工具执行前后 |
| `agent/nodes/reasoning.py` | LLM 调用前后 |
| `agent/nodes/input_parser.py` | 实体提取结果 |
| `agent/nodes/fsm_validator.py` | 验证结果 |
| `agent/nodes/output_generator.py` | 报告生成 |

**执行步骤**:

**Step 1: 创建日志配置模块**

```python
# config/logging_config.py
import logging
import sys
from typing import Optional

def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """配置应用日志"""

    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_format:
        # 结构化 JSON 日志格式
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"module": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # 开发环境可读格式
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
```

**Step 2: 在关键节点添加日志**

```python
# agent/nodes/tool_executor.py
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def execute_tool(state: AgentState) -> AgentState:
    action = state.get("next_action")
    action_input = state.get("action_input", {})

    logger.info(f"执行工具: {action}", extra={
        "tool": action,
        "inputs": str(action_input)[:200],  # 截断长输入
        "session_id": state.get("session_id"),
    })

    start_time = datetime.now()

    try:
        tool = tool_registry.get(action)
        result = tool.execute(state, action_input)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"工具执行成功: {action}", extra={
            "tool": action,
            "duration_ms": round(duration_ms, 2),
            "observation_length": len(result.get("observation", "")),
        })

        return {**state, "tool_result": result}

    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.error(f"工具执行失败: {action}", extra={
            "tool": action,
            "duration_ms": round(duration_ms, 2),
            "error_type": type(e).__name__,
            "error_message": str(e),
        }, exc_info=True)

        return {**state, "tool_result": {"observation": f"工具执行失败: {str(e)}", "error": True}}
```

**Step 3: 添加日志到其他关键节点**

```python
# agent/nodes/reasoning.py
logger.debug(f"LLM 输入 prompt 长度: {len(prompt)}")
logger.info(f"LLM 调用完成, 响应长度: {len(response)}, tokens: {usage}")

# agent/nodes/input_parser.py
logger.info(f"实体提取完成", extra={
    "entities_count": len(entities),
    "entities": list(entities.keys()),
})

# agent/nodes/fsm_validator.py
logger.info(f"FSM 验证结果: {result.valid}", extra={
    "current_state": current_state,
    "errors": result.errors,
    "warnings": result.warnings,
})
```

**验收标准**:
- [ ] 每个 Agent 节点都有日志输出
- [ ] 日志包含执行时间、状态、错误信息
- [ ] 支持 JSON 格式输出（生产环境）
- [ ] 日志级别可配置

**预估工时**: 6小时

---

### 1.3 添加 API 认证 [P0-安全]

**问题**: API 端点无身份验证，存在安全风险

**涉及文件**:
| 文件 | 修改内容 |
|------|----------|
| `apps/api/main.py` | 添加认证中间件 |
| `apps/api/auth.py` | 新建认证模块 |
| `config/settings.py` | 添加认证配置 |

**执行步骤**:

**Step 1: 添加认证配置**

```python
# config/settings.py 新增
class Settings(BaseSettings):
    # ... 现有配置 ...

    # API 认证配置
    API_KEY_ENABLED: bool = Field(default=True, description="是否启用 API Key 认证")
    API_KEYS: list[str] = Field(default=[], description="允许的 API Keys")
    JWT_SECRET: str = Field(default="change-me-in-production", description="JWT 密钥")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=60)

    # 速率限制
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="每分钟最大请求数")
```

**Step 2: 创建认证模块**

```python
# apps/api/auth.py
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

from config.settings import get_settings

settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """验证 API Key"""
    if not settings.API_KEY_ENABLED:
        return "anonymous"

    if not api_key:
        raise HTTPException(status_code=401, detail="缺少 API Key")

    if api_key not in settings.API_KEYS:
        raise HTTPException(status_code=403, detail="无效的 API Key")

    return api_key


async def verify_jwt_token(token: str = Security(bearer_scheme)) -> dict:
    """验证 JWT Token"""
    if not token:
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    try:
        payload = jwt.decode(
            token.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"令牌无效: {str(e)}")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
```

**Step 3: 添加速率限制**

```python
# apps/api/rate_limit.py
from fastapi import HTTPException, Request
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

from config.settings import get_settings

settings = get_settings()

# 简单的内存速率限制器（生产环境应使用 Redis）
request_counts: dict[str, list[datetime]] = defaultdict(list)
lock = asyncio.Lock()


async def rate_limit_middleware(request: Request):
    """速率限制中间件"""
    if not settings.RATE_LIMIT_ENABLED:
        return

    client_ip = request.client.host
    now = datetime.now()
    window_start = now - timedelta(minutes=1)

    async with lock:
        # 清理过期记录
        request_counts[client_ip] = [
            t for t in request_counts[client_ip] if t > window_start
        ]

        # 检查是否超限
        if len(request_counts[client_ip]) >= settings.RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，每分钟最多 {settings.RATE_LIMIT_REQUESTS} 次"
            )

        # 记录请求
        request_counts[client_ip].append(now)
```

**Step 4: 应用到 API 路由**

```python
# apps/api/main.py
from fastapi import FastAPI, Depends
from apps.api.auth import verify_api_key
from apps.api.rate_limit import rate_limit_middleware

app = FastAPI(title="AERO Agent API")

# 需要认证的路由
@app.post("/event/start", dependencies=[Depends(verify_api_key), Depends(rate_limit_middleware)])
async def start_event(request: EventStartRequest):
    ...

@app.post("/event/chat", dependencies=[Depends(verify_api_key), Depends(rate_limit_middleware)])
async def chat(request: ChatRequest):
    ...

# 公开路由（无需认证）
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**验收标准**:
- [ ] 无 API Key 请求返回 401
- [ ] 无效 API Key 请求返回 403
- [ ] 超过速率限制返回 429
- [ ] `/health` 端点可公开访问
- [ ] 添加认证相关的单元测试

**预估工时**: 6小时

---

### 1.4 实现输入验证框架 [P0-安全]

**问题**: 工具输入无验证，存在注入风险

**涉及文件**:
| 文件 | 修改内容 |
|------|----------|
| `tools/base.py` | 添加输入验证基类 |
| `tools/information/*.py` | 添加输入模型 |
| `tools/spatial/*.py` | 添加输入模型 |
| `tools/assessment/*.py` | 添加输入模型 |

**执行步骤**:

**Step 1: 定义输入/输出基类**

```python
# tools/schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
import re


class ToolInput(BaseModel):
    """工具输入基类"""

    class Config:
        extra = "forbid"  # 禁止额外字段


class ToolOutput(BaseModel):
    """工具输出基类"""
    observation: str = Field(..., description="工具执行结果描述")
    success: bool = Field(default=True, description="是否执行成功")
    error: Optional[str] = Field(default=None, description="错误信息")
    data: Optional[dict] = Field(default=None, description="结构化数据")


# 通用验证器
def sanitize_string(value: str, max_length: int = 1000) -> str:
    """清理字符串输入"""
    if not isinstance(value, str):
        raise ValueError("必须是字符串")

    # 移除潜在危险字符
    value = re.sub(r'[<>"\']', '', value)

    # 截断过长输入
    if len(value) > max_length:
        value = value[:max_length]

    return value.strip()


def validate_position(value: str) -> str:
    """验证机位/位置格式"""
    if not value:
        raise ValueError("位置不能为空")

    # 允许的格式: 数字、字母+数字、滑行道名称等
    pattern = r'^[A-Za-z0-9_\-]{1,20}$'
    if not re.match(pattern, value):
        raise ValueError(f"位置格式无效: {value}")

    return value.upper()


def validate_flight_number(value: str) -> str:
    """验证航班号格式"""
    if not value:
        raise ValueError("航班号不能为空")

    # 标准航班号格式: 2-3字母 + 1-4数字
    pattern = r'^[A-Z]{2,3}\d{1,4}[A-Z]?$'
    normalized = value.upper().replace(" ", "")

    if not re.match(pattern, normalized):
        raise ValueError(f"航班号格式无效: {value}")

    return normalized
```

**Step 2: 为工具定义具体输入模型**

```python
# tools/information/schemas.py
from pydantic import Field, field_validator
from tools.schemas import ToolInput, sanitize_string, validate_flight_number


class FlightPlanLookupInput(ToolInput):
    """航班计划查询输入"""
    flight_no: str = Field(..., description="航班号", min_length=3, max_length=10)

    @field_validator("flight_no")
    @classmethod
    def validate_flight_no(cls, v: str) -> str:
        return validate_flight_number(v)


class AskForDetailInput(ToolInput):
    """询问详情输入"""
    question: str = Field(..., description="问题内容", min_length=1, max_length=500)
    field_name: str = Field(..., description="字段名称", min_length=1, max_length=50)

    @field_validator("question", "field_name")
    @classmethod
    def sanitize(cls, v: str) -> str:
        return sanitize_string(v)


# tools/spatial/schemas.py
from pydantic import Field, field_validator
from tools.schemas import ToolInput, validate_position
from typing import Optional


class CalculateImpactZoneInput(ToolInput):
    """计算影响区域输入"""
    position: str = Field(..., description="事故位置")
    fluid_type: str = Field(..., description="油液类型")
    risk_level: str = Field(default="MEDIUM", description="风险等级")

    @field_validator("position")
    @classmethod
    def validate_pos(cls, v: str) -> str:
        return validate_position(v)

    @field_validator("fluid_type")
    @classmethod
    def validate_fluid(cls, v: str) -> str:
        allowed = {"FUEL", "HYDRAULIC", "OIL"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"油液类型必须是: {allowed}")
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"风险等级必须是: {allowed}")
        return v
```

**Step 3: 更新 BaseTool 使用验证**

```python
# tools/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
from pydantic import ValidationError
from tools.schemas import ToolInput, ToolOutput
import logging

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """工具基类"""

    name: str
    description: str
    input_schema: Optional[Type[ToolInput]] = None  # 子类可覆盖

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具（带输入验证）"""

        # 验证输入
        if self.input_schema:
            try:
                validated_inputs = self.input_schema(**inputs)
                inputs = validated_inputs.model_dump()
            except ValidationError as e:
                logger.warning(f"工具 {self.name} 输入验证失败: {e}")
                return {
                    "observation": f"输入参数无效: {e.errors()[0]['msg']}",
                    "error": True,
                }

        # 执行实际逻辑
        return self._execute(state, inputs)

    @abstractmethod
    def _execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """子类实现的具体执行逻辑"""
        pass
```

**Step 4: 更新工具实现**

```python
# tools/information/flight_plan_lookup.py
from tools.base import BaseTool
from tools.information.schemas import FlightPlanLookupInput


class FlightPlanLookupTool(BaseTool):
    name = "flight_plan_lookup"
    description = "从航班计划数据查询航班"
    input_schema = FlightPlanLookupInput  # 指定输入模型

    def _execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        flight_no = inputs["flight_no"]  # 已验证
        # ... 原有逻辑 ...
```

**验收标准**:
- [ ] 所有工具都有输入验证
- [ ] 无效输入返回友好错误信息
- [ ] 验证规则有单元测试
- [ ] 不允许 SQL/命令注入

**预估工时**: 8小时

---

## Phase 2: 稳定性改进（第 3-4 周）

### 2.1 实现持久化存储 [P1-重要]

**问题**: 当前仅内存存储，进程重启丢失数据

**涉及文件**:
| 文件 | 修改内容 |
|------|----------|
| `agent/storage/session_store.py` | 添加 PostgreSQL/Redis 实现 |
| `config/settings.py` | 添加数据库配置 |
| `requirements.txt` | 添加依赖 |

**执行步骤**:

**Step 1: 添加依赖**

```bash
# requirements.txt 新增
asyncpg>=0.29.0
redis>=5.0.0
sqlalchemy>=2.0.0
```

**Step 2: 添加数据库配置**

```python
# config/settings.py 新增
class Settings(BaseSettings):
    # 存储配置
    STORAGE_BACKEND: str = Field(default="memory", description="存储后端: memory, postgres, redis")

    # PostgreSQL 配置
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_USER: str = Field(default="aero")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_DB: str = Field(default="aero_agent")

    @property
    def postgres_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis 配置
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
```

**Step 3: 实现 PostgreSQL 存储**

```python
# agent/storage/postgres_store.py
from typing import Optional, Dict, Any
from datetime import datetime
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, JSON, select
from sqlalchemy.ext.declarative import declarative_base

from agent.storage.base import SessionStore
from config.settings import get_settings

Base = declarative_base()


class SessionModel(Base):
    """会话数据模型"""
    __tablename__ = "sessions"

    session_id = Column(String(64), primary_key=True)
    state = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class PostgresSessionStore(SessionStore):
    """PostgreSQL 会话存储"""

    def __init__(self):
        settings = get_settings()
        self.engine = create_async_engine(settings.postgres_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """初始化数据库表"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        async with self.async_session() as session:
            result = await session.execute(
                select(SessionModel).where(SessionModel.session_id == session_id)
            )
            row = result.scalar_one_or_none()
            if row:
                return row.state
            return None

    async def set(self, session_id: str, state: Dict[str, Any]) -> None:
        """保存会话"""
        async with self.async_session() as session:
            existing = await session.get(SessionModel, session_id)
            if existing:
                existing.state = state
                existing.updated_at = datetime.utcnow()
            else:
                session.add(SessionModel(session_id=session_id, state=state))
            await session.commit()

    async def delete(self, session_id: str) -> None:
        """删除会话"""
        async with self.async_session() as session:
            existing = await session.get(SessionModel, session_id)
            if existing:
                await session.delete(existing)
                await session.commit()
```

**Step 4: 实现存储工厂**

```python
# agent/storage/factory.py
from agent.storage.base import SessionStore
from agent.storage.memory_store import MemorySessionStore
from agent.storage.postgres_store import PostgresSessionStore
from config.settings import get_settings


def get_session_store() -> SessionStore:
    """根据配置返回存储实例"""
    settings = get_settings()

    if settings.STORAGE_BACKEND == "postgres":
        return PostgresSessionStore()
    elif settings.STORAGE_BACKEND == "redis":
        from agent.storage.redis_store import RedisSessionStore
        return RedisSessionStore()
    else:
        return MemorySessionStore()
```

**验收标准**:
- [ ] 支持 PostgreSQL 存储
- [ ] 支持 Redis 存储（可选）
- [ ] 进程重启后数据不丢失
- [ ] 有存储层的集成测试

**预估工时**: 12小时

---

### 2.2 完善类型注解 [P1-质量]

**目标**: 类型注解覆盖率从 60% 提升到 90%

**涉及文件**:
- `agent/state.py`
- `agent/nodes/*.py`
- `tools/base.py`
- `tools/*/*.py`

**执行步骤**:

**Step 1: 运行 mypy 获取当前状态**

```bash
mypy . --ignore-missing-imports --show-error-codes 2>&1 | tee mypy_report.txt
cat mypy_report.txt | grep "error:" | wc -l  # 统计错误数
```

**Step 2: 定义核心类型**

```python
# agent/types.py
from typing import TypedDict, Optional, List, Dict, Any, Literal
from datetime import datetime


class IncidentInfo(TypedDict, total=False):
    """事故信息类型"""
    scenario: str
    position: str
    fluid_type: Optional[str]
    leak_size: Optional[str]
    incident_time: Optional[str]
    flight_no: Optional[str]
    aircraft_type: Optional[str]


class RiskAssessment(TypedDict, total=False):
    """风险评估类型"""
    level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    score: int
    factors: List[str]
    timestamp: str


class SpatialAnalysis(TypedDict, total=False):
    """空间分析类型"""
    affected_stands: List[str]
    affected_taxiways: List[str]
    affected_runways: List[str]
    impact_radius: int


class FlightImpact(TypedDict, total=False):
    """航班影响类型"""
    time_window: Dict[str, str]
    affected_flights: List[Dict[str, Any]]
    statistics: Dict[str, Any]


class AgentState(TypedDict, total=False):
    """Agent 状态类型（完整定义）"""
    session_id: str
    scenario: str
    incident: IncidentInfo
    checklist: Dict[str, Any]
    risk_assessment: RiskAssessment
    spatial_analysis: SpatialAnalysis
    flight_impact: FlightImpact
    reference_flight: Dict[str, Any]
    fsm_state: str
    messages: List[Dict[str, str]]
    next_action: Optional[str]
    action_input: Optional[Dict[str, Any]]
    tool_result: Optional[Dict[str, Any]]
    final_report: Optional[str]
```

**Step 3: 更新节点函数签名**

```python
# agent/nodes/tool_executor.py
from agent.types import AgentState

def execute_tool(state: AgentState) -> AgentState:
    """执行工具并更新状态"""
    action: str = state.get("next_action", "")
    action_input: Dict[str, Any] = state.get("action_input", {})

    # ... 实现 ...

    return AgentState(**updated_state)
```

**Step 4: 逐模块修复类型错误**

```bash
# 分模块修复
mypy agent/nodes/ --ignore-missing-imports
mypy tools/information/ --ignore-missing-imports
mypy tools/spatial/ --ignore-missing-imports
mypy tools/assessment/ --ignore-missing-imports
```

**验收标准**:
- [ ] `mypy . --ignore-missing-imports` 错误数 < 10
- [ ] 核心类型有完整定义
- [ ] IDE 能提供准确的类型提示

**预估工时**: 8小时

---

### 2.3 实现错误处理框架 [P1-可靠性]

**问题**: 缺少全局错误处理、重试机制和降级策略

**涉及文件**:
| 文件 | 修改内容 |
|------|----------|
| `agent/error_handling.py` | 新建错误处理模块 |
| `agent/graph.py` | 添加全局错误处理 |
| `tools/base.py` | 添加重试装饰器 |

**执行步骤**:

**Step 1: 定义错误类型**

```python
# agent/exceptions.py
class AeroAgentError(Exception):
    """Agent 基础异常"""
    pass


class ToolExecutionError(AeroAgentError):
    """工具执行异常"""
    def __init__(self, tool_name: str, message: str, retryable: bool = False):
        self.tool_name = tool_name
        self.retryable = retryable
        super().__init__(f"工具 {tool_name} 执行失败: {message}")


class LLMError(AeroAgentError):
    """LLM 调用异常"""
    def __init__(self, message: str, retryable: bool = True):
        self.retryable = retryable
        super().__init__(f"LLM 调用失败: {message}")


class ValidationError(AeroAgentError):
    """验证异常"""
    pass


class FSMTransitionError(AeroAgentError):
    """FSM 状态转换异常"""
    pass
```

**Step 2: 实现重试装饰器**

```python
# agent/retry.py
import asyncio
import functools
import logging
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """重试装饰器（支持指数退避）"""

    def decorator(func: Callable):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts:
                        wait_time = delay * (backoff ** (attempt - 1))
                        logger.warning(
                            f"重试 {func.__name__} (尝试 {attempt}/{max_attempts}), "
                            f"等待 {wait_time:.1f}s, 错误: {e}"
                        )

                        if on_retry:
                            on_retry(attempt, e)

                        import time
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} 重试耗尽, 最后错误: {e}")

            raise last_exception

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts:
                        wait_time = delay * (backoff ** (attempt - 1))
                        logger.warning(
                            f"重试 {func.__name__} (尝试 {attempt}/{max_attempts}), "
                            f"等待 {wait_time:.1f}s, 错误: {e}"
                        )
                        await asyncio.sleep(wait_time)

            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
```

**Step 3: 实现断路器**

```python
# agent/circuit_breaker.py
import time
from enum import Enum
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开


class CircuitBreaker:
    """断路器模式实现"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable, *args, **kwargs):
        """执行函数（带断路器保护）"""

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"断路器 {self.name} 进入半开状态")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"断路器 {self.name} 已熔断")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"断路器 {self.name} 恢复正常")
            self.state = CircuitState.CLOSED

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            logger.warning(f"断路器 {self.name} 触发熔断")
            self.state = CircuitState.OPEN
```

**Step 4: 在 Agent Graph 中应用**

```python
# agent/graph.py
from agent.exceptions import ToolExecutionError, LLMError
from agent.retry import retry
from agent.circuit_breaker import CircuitBreaker

# LLM 调用断路器
llm_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60, name="llm")


@retry(max_attempts=3, delay=1.0, exceptions=(LLMError,))
def call_llm_with_retry(prompt: str) -> str:
    """带重试的 LLM 调用"""
    return llm_breaker.call(llm.invoke, prompt)
```

**验收标准**:
- [ ] 有统一的异常类型定义
- [ ] LLM 调用有重试机制
- [ ] 工具执行有错误隔离
- [ ] 有断路器防止级联失败

**预估工时**: 10小时

---

### 2.4 补充集成测试 [P1-质量]

**目标**: 集成测试覆盖率从 40% 提升到 70%

**涉及文件**:
- `tests/integration/test_oil_spill_flow.py`
- `tests/integration/test_bird_strike_flow.py`
- `tests/integration/test_api_endpoints.py`

**执行步骤**:

**Step 1: 创建测试 Fixtures**

```python
# tests/conftest.py
import pytest
from typing import Dict, Any

@pytest.fixture
def oil_spill_state() -> Dict[str, Any]:
    """漏油场景测试状态"""
    return {
        "session_id": "test-session-001",
        "scenario": "oil_spill",
        "incident": {
            "position": "501",
            "fluid_type": "FUEL",
            "leak_size": "LARGE",
            "incident_time": "2026-01-06 10:00:00",
        },
        "risk_assessment": {
            "level": "HIGH",
            "score": 85,
        },
        "spatial_analysis": {
            "affected_stands": ["stand_501", "stand_502"],
            "affected_taxiways": ["taxiway_A3"],
            "affected_runways": ["runway_24R"],
        },
        "messages": [],
    }


@pytest.fixture
def mock_llm_response(mocker):
    """Mock LLM 响应"""
    def _mock(content: str):
        mock = mocker.MagicMock()
        mock.content = content
        return mocker.patch("config.llm_config.get_llm_client", return_value=mock)
    return _mock
```

**Step 2: 端到端流程测试**

```python
# tests/integration/test_oil_spill_flow.py
import pytest
from agent.graph import create_agent_graph
from agent.state import AgentState


class TestOilSpillFlow:
    """漏油场景端到端测试"""

    @pytest.mark.asyncio
    async def test_complete_flow(self, oil_spill_state, mock_llm_response):
        """测试完整处理流程"""
        # 准备
        mock_llm_response("我需要更多信息...")
        graph = create_agent_graph()

        # 执行
        final_state = await graph.ainvoke(oil_spill_state)

        # 验证
        assert final_state["fsm_state"] != "INIT"
        assert "risk_assessment" in final_state
        assert final_state.get("tool_result") is not None

    @pytest.mark.asyncio
    async def test_high_risk_notification(self, oil_spill_state):
        """测试高风险情况的消防通知"""
        oil_spill_state["risk_assessment"]["level"] = "HIGH"

        # ... 执行流程 ...

        # 验证消防部门被通知
        assert "消防" in str(final_state.get("notifications", []))

    @pytest.mark.asyncio
    async def test_error_recovery(self, oil_spill_state, mock_llm_response):
        """测试错误恢复"""
        # 模拟 LLM 失败后恢复
        mock_llm_response(side_effect=[Exception("API Error"), "正常响应"])

        # ... 执行并验证重试成功 ...
```

**Step 3: API 端点测试**

```python
# tests/integration/test_api_endpoints.py
import pytest
from httpx import AsyncClient
from apps.api.main import app


class TestAPIEndpoints:
    """API 端点集成测试"""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """健康检查端点"""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_start_event_requires_auth(self, client):
        """启动事件需要认证"""
        response = await client.post("/event/start", json={})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_start_event_with_valid_key(self, client):
        """使用有效 API Key 启动事件"""
        response = await client.post(
            "/event/start",
            json={"scenario": "oil_spill", "user_input": "501机位漏油"},
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 200
        assert "session_id" in response.json()
```

**验收标准**:
- [ ] 每个场景有完整流程测试
- [ ] API 端点有正/负测试
- [ ] 有错误恢复测试
- [ ] 测试覆盖率报告 > 70%

**预估工时**: 12小时

---

## Phase 3: 可观测性（第 5-6 周）

### 3.1 健康检查端点 [P2-运维]

**执行步骤**:

```python
# apps/api/health.py
from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """基础健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
    }

@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """就绪检查（检查依赖服务）"""
    checks = {
        "database": await check_database(),
        "llm_api": await check_llm_api(),
        "topology_data": check_topology_data(),
    }

    all_healthy = all(c["healthy"] for c in checks.values())

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }

@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """存活检查"""
    return {"status": "alive"}
```

**预估工时**: 4小时

---

### 3.2 Prometheus 指标 [P2-监控]

**执行步骤**:

```python
# apps/api/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Response

# 定义指标
REQUEST_COUNT = Counter(
    "aero_agent_requests_total",
    "Total requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "aero_agent_request_duration_seconds",
    "Request latency",
    ["method", "endpoint"]
)

TOOL_EXECUTION_COUNT = Counter(
    "aero_agent_tool_executions_total",
    "Tool executions",
    ["tool_name", "status"]
)

ACTIVE_SESSIONS = Gauge(
    "aero_agent_active_sessions",
    "Number of active sessions"
)

LLM_CALL_COUNT = Counter(
    "aero_agent_llm_calls_total",
    "LLM API calls",
    ["status"]
)

LLM_CALL_LATENCY = Histogram(
    "aero_agent_llm_call_duration_seconds",
    "LLM call latency"
)


# 指标端点
@router.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

**预估工时**: 6小时

---

### 3.3 结构化日志配置 [P2-运维]

**目标**: JSON 格式日志，支持 ELK/Loki 聚合

```python
# config/logging_config.py
import logging
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON 日志格式化器"""

    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "extra"):
            log_obj.update(record.extra)

        # 添加异常信息
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)
```

**预估工时**: 4小时

---

## Phase 4: 生产部署（第 7-8 周）

### 4.1 Docker 化 [P2-部署]

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 设置环境变量
ENV PYTHONPATH=/app
ENV LOG_FORMAT=json

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - STORAGE_BACKEND=postgres
      - POSTGRES_HOST=db
      - LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=aero
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=aero_agent

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

**预估工时**: 8小时

---

### 4.2 CI/CD 流程 [P2-自动化]

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install black isort mypy
      - run: black --check .
      - run: isort --check .
      - run: mypy . --ignore-missing-imports

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --cov=agent,tools --cov-report=xml
      - uses: codecov/codecov-action@v3

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with:
          push: false
          tags: aero-agent:${{ github.sha }}
```

**预估工时**: 6小时

---

## 工时汇总

| 阶段 | 任务 | 预估工时 |
|------|------|----------|
| **Phase 1** | 紧急修复 | **24小时** |
| 1.1 | 修复异常处理 | 4h |
| 1.2 | 添加结构化日志 | 6h |
| 1.3 | 添加 API 认证 | 6h |
| 1.4 | 实现输入验证 | 8h |
| **Phase 2** | 稳定性改进 | **42小时** |
| 2.1 | 实现持久化存储 | 12h |
| 2.2 | 完善类型注解 | 8h |
| 2.3 | 实现错误处理框架 | 10h |
| 2.4 | 补充集成测试 | 12h |
| **Phase 3** | 可观测性 | **14小时** |
| 3.1 | 健康检查端点 | 4h |
| 3.2 | Prometheus 指标 | 6h |
| 3.3 | 结构化日志配置 | 4h |
| **Phase 4** | 生产部署 | **14小时** |
| 4.1 | Docker 化 | 8h |
| 4.2 | CI/CD 流程 | 6h |
| **总计** | | **94小时** |

---

## 执行检查清单

### Phase 1 完成标准
- [ ] `grep -rn "except:" --include="*.py" | grep -v "except.*:"` 返回空
- [ ] 每个 Agent 节点都有日志输出
- [ ] API 认证测试通过
- [ ] 输入验证测试通过

### Phase 2 完成标准
- [ ] 进程重启后会话数据不丢失
- [ ] `mypy` 错误数 < 10
- [ ] 工具执行失败有重试
- [ ] 测试覆盖率 > 70%

### Phase 3 完成标准
- [ ] `/health` 端点可访问
- [ ] `/metrics` 返回 Prometheus 格式
- [ ] 日志为 JSON 格式

### Phase 4 完成标准
- [ ] `docker-compose up` 可启动服务
- [ ] CI 流程通过
- [ ] 有部署文档

---

## 附录: 快速开始命令

```bash
# 克隆并安装
git clone <repo>
cd AERO_Agent
pip install -e ".[dev]"

# 运行代码检查
black . --check
isort . --check
mypy . --ignore-missing-imports

# 运行测试
pytest tests/ -v --cov=agent,tools

# 查找待修复问题
grep -rn "except:" --include="*.py" | grep -v "except.*:"
grep -rn "print(" --include="*.py" | grep -v test

# 启动开发服务
uvicorn apps.api.main:app --reload
```

---

**文档版本**: v1.0.0
**最后更新**: 2026-01-20
