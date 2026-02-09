"""
FastAPI 入口
"""
# 在最开始加载环境变量，确保 LangSmith 等配置生效
from dotenv import load_dotenv
load_dotenv()

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import json
import asyncio
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent.graph import agent, get_agent_config
from agent.state import create_initial_state
from agent.storage import get_session_store
from apps.api.auth import get_current_user
from apps.api.analyze import router as analyze_router
from apps.api.rate_limit import rate_limit_check
from config.logging_config import setup_logging
from config.settings import settings

# 初始化日志配置
setup_logging()
logger = logging.getLogger(__name__)

backend = settings.STORAGE_BACKEND or settings.SESSION_STORE_BACKEND
session_store = get_session_store(backend)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GEOJSON_LAYER_PATHS = {
    "runway_surface": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "runway" / "tianfu_runway_surface.geojson",
    "runway_centerline": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "runway" / "tianfu_runway_centerline.geojson",
    "runway_label": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "runway" / "tianfu_runway_label.geojson",
    "taxiway_surface": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "taxiway" / "tianfu_taxiway_surface.geojson",
    "taxiway_centerline": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "taxiway" / "tianfu_taxiway_centerline.geojson",
    "taxiway_label": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "taxiway" / "tianfu_taxiway_label.geojson",
    "stand_surface": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "stand" / "tianfu_stand_surface.geojson",
    "stand_label": PROJECT_ROOT / "outputs" / "spatial_data" / "geojson" / "stand" / "tianfu_stand_label.geojson",
}


def get_fsm_states_for_scenario(scenario_type: str) -> List[Dict[str, Any]]:
    if not scenario_type:
        return []
    from scenarios.base import ScenarioRegistry

    scenario = ScenarioRegistry.get(scenario_type)
    if not scenario:
        return []
    states = scenario.fsm_states or []
    return sorted(states, key=lambda item: item.get("order", 0))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await session_store.init()
    yield


app = FastAPI(
    title="机场应急响应智能 Agent",
    description="融合 ReAct Agent + FSM 验证的机坪特情处置系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.session_store = session_store
app.include_router(analyze_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        status_code = response.status_code if response else 500
        logger.info(
            "request_id=%s method=%s path=%s status=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
        )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error path=%s", request.url.path)
    detail = str(exc) if settings.DEBUG else "Internal Server Error"
    return JSONResponse(status_code=500, content={"detail": detail})


# 请求/响应模型
class EventRequest(BaseModel):
    """事件请求"""
    message: str = Field(..., description="用户输入消息")
    session_id: Optional[str] = Field(None, description="会话ID，不传则新建")
    scenario_type: Optional[str] = Field(None, description="场景类型")


class ParseRequest(BaseModel):
    """解析请求（仅提取信息，不启动流程）"""
    message: str = Field(..., description="用户输入消息")
    scenario_type: Optional[str] = Field(None, description="场景类型")


class ParseResponse(BaseModel):
    scenario_type: str
    incident: Dict[str, Any]
    checklist: Dict[str, bool]
    enrichment_observation: Optional[str] = None


class ToolCallInfo(BaseModel):
    """工具调用信息"""
    id: str
    name: str
    input: dict = {}
    output: Optional[str] = None
    status: str = "completed"


class ReasoningStepInfo(BaseModel):
    """推理步骤信息"""
    step: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    observation: Optional[str] = None


class EventResponse(BaseModel):
    """事件响应"""
    session_id: str
    status: str
    message: str
    report: Optional[dict] = None
    fsm_state: str
    checklist: dict
    risk_level: Optional[str] = None
    next_question: Optional[str] = None
    scenario_type: Optional[str] = None
    incident: Optional[dict] = None
    fsm_states: List[Dict[str, Any]] = []
    # 新增：工具调用和推理过程
    tool_calls: List[ToolCallInfo] = []
    reasoning_steps: List[ReasoningStepInfo] = []
    current_thought: Optional[str] = None
    spatial_analysis: Optional[dict] = None
    flight_impact_prediction: Optional[dict] = None


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="用户消息")


@app.get("/")
async def root():
    """健康检查（公开端点）"""
    return {
        "service": "Airport Emergency Agent",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """健康检查端点（公开）"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@app.get("/spatial/geojson/{layer_name}")
async def get_geojson_layer(
    layer_name: str,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    获取机场拓扑 GeoJSON 图层
    """
    path = GEOJSON_LAYER_PATHS.get(layer_name)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="GeoJSON layer not found")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        detail = str(exc) if settings.DEBUG else "Failed to load GeoJSON layer"
        raise HTTPException(status_code=500, detail=detail)

    return JSONResponse(content=data)


@app.post("/event/start", response_model=EventResponse)
async def start_event(
    request: EventRequest,
    req: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    启动新的事件处理
    """
    # 生成会话ID
    session_id = request.session_id or str(uuid.uuid4())
    
    # 清理过期会话
    await session_store.cleanup_expired()

    # 创建初始状态
    state = create_initial_state(
        session_id=session_id,
        scenario_type=request.scenario_type or "",
        initial_message=request.message,
    )
    
    # 运行 Agent
    try:
        result = agent.invoke(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # 保存会话
    await session_store.set(session_id, result, settings.SESSION_TTL_SECONDS)
    
    # 提取工具调用信息
    tool_calls = []
    reasoning_steps_raw = result.get("reasoning_steps", [])
    for i, step in enumerate(reasoning_steps_raw):
        if step.get("action"):
            tool_calls.append(ToolCallInfo(
                id=f"tool-{i}",
                name=step.get("action", ""),
                input=step.get("action_input", {}),
                output=step.get("observation", ""),
                status="completed"
            ))

    # 提取推理步骤
    reasoning_steps = [
        ReasoningStepInfo(
            step=i + 1,
            thought=step.get("thought", ""),
            action=step.get("action"),
            action_input=step.get("action_input"),
            observation=step.get("observation"),
        )
        for i, step in enumerate(reasoning_steps_raw)
    ]

    # 构建响应
    scenario_type = result.get("scenario_type") or request.scenario_type or ""
    fsm_states = get_fsm_states_for_scenario(scenario_type)
    response = EventResponse(
        session_id=session_id,
        status="processing" if not result.get("is_complete") else "completed",
        message=result.get("final_answer", "正在处理中..."),
        report=result.get("final_report") if result.get("is_complete") else None,
        fsm_state=result.get("fsm_state", "INIT"),
        checklist=result.get("checklist", {}),
        risk_level=result.get("risk_assessment", {}).get("level"),
        scenario_type=scenario_type or None,
        incident=result.get("incident"),
        fsm_states=fsm_states,
        tool_calls=tool_calls,
        reasoning_steps=reasoning_steps,
        current_thought=result.get("current_thought"),
        spatial_analysis=result.get("spatial_analysis"),
        flight_impact_prediction=result.get("flight_impact_prediction"),
    )

    # 检查是否需要追问
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            response.next_question = msg.get("content")
            break

    return response


@app.post("/event/parse", response_model=ParseResponse)
async def parse_event(
    request: ParseRequest,
    _: dict = Depends(get_current_user),
):
    """解析输入并返回提取字段，不启动完整流程"""
    from agent.nodes.input_parser import input_parser_node, identify_scenario

    scenario_type = request.scenario_type or identify_scenario(request.message)
    state = create_initial_state(
        session_id=f"parse-{uuid.uuid4().hex[:8]}",
        scenario_type=scenario_type,
        initial_message=request.message,
    )

    updates = input_parser_node(state)
    state.update(updates)

    return ParseResponse(
        scenario_type=state.get("scenario_type", scenario_type),
        incident=state.get("incident", {}),
        checklist=state.get("checklist", {}),
        enrichment_observation=state.get("enrichment_observation"),
    )

@app.post("/event/chat", response_model=EventResponse)
async def chat_event(
    request: ChatRequest,
    req: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    继续对话
    """
    session_id = request.session_id
    
    await session_store.cleanup_expired()

    # 获取当前状态
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 添加用户消息
    messages = state.get("messages", [])
    messages.append({"role": "user", "content": request.message})
    state["messages"] = messages
    
    # 重置完成状态，继续处理
    state["is_complete"] = False
    state["next_node"] = "input_parser"
    
    # 运行 Agent
    try:
        result = agent.invoke(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # 更新会话
    await session_store.set(session_id, result, settings.SESSION_TTL_SECONDS)

    # 提取工具调用信息
    tool_calls = []
    reasoning_steps_raw = result.get("reasoning_steps", [])
    for i, step in enumerate(reasoning_steps_raw):
        if step.get("action"):
            tool_calls.append(ToolCallInfo(
                id=f"tool-{i}",
                name=step.get("action", ""),
                input=step.get("action_input", {}),
                output=step.get("observation", ""),
                status="completed"
            ))

    # 提取推理步骤
    reasoning_steps = [
        ReasoningStepInfo(
            step=i + 1,
            thought=step.get("thought", ""),
            action=step.get("action"),
            action_input=step.get("action_input"),
            observation=step.get("observation"),
        )
        for i, step in enumerate(reasoning_steps_raw)
    ]

    # 构建响应
    scenario_type = result.get("scenario_type") or ""
    fsm_states = get_fsm_states_for_scenario(scenario_type)
    response = EventResponse(
        session_id=session_id,
        status="processing" if not result.get("is_complete") else "completed",
        message=result.get("final_answer", "正在处理中..."),
        report=result.get("final_report") if result.get("is_complete") else None,
        fsm_state=result.get("fsm_state", "INIT"),
        checklist=result.get("checklist", {}),
        risk_level=result.get("risk_assessment", {}).get("level"),
        scenario_type=scenario_type or None,
        incident=result.get("incident"),
        fsm_states=fsm_states,
        tool_calls=tool_calls,
        reasoning_steps=reasoning_steps,
        current_thought=result.get("current_thought"),
        spatial_analysis=result.get("spatial_analysis"),
        flight_impact_prediction=result.get("flight_impact_prediction"),
    )

    # 检查是否需要追问
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            response.next_question = msg.get("content")
            break

    return response


@app.get("/event/{session_id}")
async def get_event_status(
    session_id: str,
    request: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    获取事件状态
    """
    await session_store.cleanup_expired()

    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return {
        "session_id": session_id,
        "fsm_state": state.get("fsm_state"),
        "checklist": state.get("checklist"),
        "risk_assessment": state.get("risk_assessment"),
        "is_complete": state.get("is_complete"),
        "iteration_count": state.get("iteration_count"),
    }


@app.get("/event/{session_id}/report")
async def get_event_report(
    session_id: str,
    request: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    获取事件报告（JSON格式）
    """
    await session_store.cleanup_expired()

    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    if not state.get("final_report"):
        raise HTTPException(status_code=400, detail="报告尚未生成")

    return state.get("final_report")


@app.get("/event/{session_id}/report/markdown")
async def get_event_report_markdown(
    session_id: str,
    request: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    获取事件报告（Markdown文件格式）
    """
    await session_store.cleanup_expired()

    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    final_answer = state.get("final_answer")
    if not final_answer:
        raise HTTPException(status_code=400, detail="报告尚未生成")

    # 获取事件信息用于文件名
    incident = state.get("incident", {})
    flight_no = incident.get("flight_no", session_id[:8])

    # 生成文件名
    filename = f"机坪特情处置检查单_{flight_no}_{session_id[:8]}.md"

    from fastapi.responses import Response
    return Response(
        content=final_answer,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.delete("/event/{session_id}")
async def close_event(
    session_id: str,
    request: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    关闭事件会话
    """
    await session_store.cleanup_expired()

    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    await session_store.delete(session_id)
    
    return {"status": "closed", "session_id": session_id}


# ============================================================
# 流式接口 (SSE - Server-Sent Events)
# ============================================================

def extract_stream_event(node_name: str, state: dict) -> dict:
    """从节点执行结果中提取流式事件数据"""
    event = {
        "node": node_name,
        "timestamp": datetime.now().isoformat(),
        "fsm_state": state.get("fsm_state", "INIT"),
        "checklist": state.get("checklist", {}),
    }
    scenario_type = state.get("scenario_type", "")
    if scenario_type:
        event["scenario_type"] = scenario_type
        event["fsm_states"] = get_fsm_states_for_scenario(scenario_type)
    if state.get("incident"):
        event["incident"] = state.get("incident")

    # 提取当前推理步骤
    if state.get("current_thought"):
        event["current_thought"] = state.get("current_thought")

    # 提取当前动作
    if state.get("current_action"):
        event["current_action"] = state.get("current_action")
        event["current_action_input"] = state.get("current_action_input", {})

    # 提取观察结果
    if state.get("current_observation"):
        event["current_observation"] = state.get("current_observation")

    # 提取推理步骤
    reasoning_steps = state.get("reasoning_steps", [])
    if reasoning_steps:
        event["reasoning_steps"] = reasoning_steps

    # 提取风险评估
    if state.get("risk_assessment"):
        event["risk_assessment"] = state.get("risk_assessment")

    # 提取空间分析
    if state.get("spatial_analysis"):
        event["spatial_analysis"] = state.get("spatial_analysis")

    # 提取航班影响
    if state.get("flight_impact_prediction"):
        event["flight_impact_prediction"] = state.get("flight_impact_prediction")

    # 提取是否完成
    event["is_complete"] = state.get("is_complete", False)

    # 提取最终答案
    if state.get("final_answer"):
        event["final_answer"] = state.get("final_answer")

    # 提取agent询问消息（从messages中获取最新的assistant消息）
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            event["next_question"] = msg.get("content")
            break

    return event


async def stream_agent_execution(state: dict, session_id: str):
    """流式执行 Agent 并生成 SSE 事件"""
    try:
        # 使用 stream 方法执行 Agent
        config = get_agent_config()

        for chunk in agent.stream(state, config=config):
            # chunk 是一个字典，键是节点名称，值是该节点的输出状态
            for node_name, node_output in chunk.items():
                # 合并状态
                state.update(node_output)

                # 生成事件
                event_data = extract_stream_event(node_name, state)
                event_data["session_id"] = session_id

                # 发送 SSE 事件
                yield f"event: node_update\ndata: {json.dumps(event_data, ensure_ascii=False, default=str)}\n\n"

                # 小延迟确保前端能够处理
                await asyncio.sleep(0.05)

        # 发送完成事件
        scenario_type = state.get("scenario_type", "")
        final_event = {
            "session_id": session_id,
            "status": "completed" if state.get("is_complete") else "processing",
            "fsm_state": state.get("fsm_state", "INIT"),
            "checklist": state.get("checklist", {}),
            "risk_level": state.get("risk_assessment", {}).get("level"),
            "final_answer": state.get("final_answer", ""),
            "reasoning_steps": state.get("reasoning_steps", []),
            "incident": state.get("incident", {}),
        }
        if scenario_type:
            final_event["scenario_type"] = scenario_type
            final_event["fsm_states"] = get_fsm_states_for_scenario(scenario_type)

        # 检查是否有追问
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                final_event["next_question"] = msg.get("content")
                break

        yield f"event: complete\ndata: {json.dumps(final_event, ensure_ascii=False, default=str)}\n\n"

        # 保存会话状态
        await session_store.set(session_id, state, settings.SESSION_TTL_SECONDS)

    except Exception as e:
        logger.exception("Stream execution error")
        error_event = {
            "session_id": session_id,
            "error": str(e),
            "status": "error",
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"


@app.post("/event/start/stream")
async def start_event_stream(
    request: EventRequest,
    req: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    流式启动新的事件处理 (SSE)
    """
    session_id = request.session_id or str(uuid.uuid4())

    await session_store.cleanup_expired()

    # 创建初始状态
    state = create_initial_state(
        session_id=session_id,
        scenario_type=request.scenario_type or "",
        initial_message=request.message,
    )

    return StreamingResponse(
        stream_agent_execution(state, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@app.post("/event/chat/stream")
async def chat_event_stream(
    request: ChatRequest,
    req: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    """
    流式继续对话 (SSE)
    """
    session_id = request.session_id

    await session_store.cleanup_expired()

    # 获取当前状态
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 添加用户消息
    messages = state.get("messages", [])
    messages.append({"role": "user", "content": request.message})
    state["messages"] = messages

    # 重置完成状态，继续处理
    state["is_complete"] = False
    state["next_node"] = "input_parser"

    return StreamingResponse(
        stream_agent_execution(state, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
