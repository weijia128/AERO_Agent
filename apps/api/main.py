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
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent.graph import agent
from agent.state import create_initial_state
from agent.storage import get_session_store
from apps.api.auth import get_current_user
from apps.api.rate_limit import rate_limit_check
from config.logging_config import setup_logging
from config.settings import settings

# 初始化日志配置
setup_logging()
logger = logging.getLogger(__name__)

backend = settings.STORAGE_BACKEND or settings.SESSION_STORE_BACKEND
session_store = get_session_store(backend)


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
    scenario_type: str = Field("oil_spill", description="场景类型")


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
        scenario_type=request.scenario_type,
        initial_message=request.message,
    )
    
    # 运行 Agent
    try:
        result = agent.invoke(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # 保存会话
    await session_store.set(session_id, result, settings.SESSION_TTL_SECONDS)
    
    # 构建响应
    response = EventResponse(
        session_id=session_id,
        status="processing" if not result.get("is_complete") else "completed",
        message=result.get("final_answer", "正在处理中..."),
        report=result.get("final_report") if result.get("is_complete") else None,
        fsm_state=result.get("fsm_state", "INIT"),
        checklist=result.get("checklist", {}),
        risk_level=result.get("risk_assessment", {}).get("level"),
    )
    
    # 检查是否需要追问
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            response.next_question = msg.get("content")
            break
    
    return response


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
    
    # 构建响应
    response = EventResponse(
        session_id=session_id,
        status="processing" if not result.get("is_complete") else "completed",
        message=result.get("final_answer", "正在处理中..."),
        report=result.get("final_report") if result.get("is_complete") else None,
        fsm_state=result.get("fsm_state", "INIT"),
        checklist=result.get("checklist", {}),
        risk_level=result.get("risk_assessment", {}).get("level"),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
