from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.graph import agent, get_agent_config
from agent.nodes.input_parser import identify_scenario, input_parser_node
from agent.state import create_initial_state
from apps.api.auth import get_current_user
from apps.api.external_recommendation import build_external_recommendation
from apps.api.rate_limit import rate_limit_check
from config.settings import settings
from scenarios.base import ScenarioRegistry

router = APIRouter(prefix="/analyze", tags=["external_analyze"])


class AnalyzeParseRequest(BaseModel):
    message: str = Field(..., description="用户输入消息")
    scenario_type: Optional[str] = Field(None, description="场景类型（可选）")


class AnalyzeParseResponse(BaseModel):
    scenario_type: str
    incident: Dict[str, Any]
    checklist: Dict[str, Any]
    missing_fields: List[str]


class AnalyzeStartRequest(BaseModel):
    message: str = Field(..., description="用户输入消息")
    scenario_type: Optional[str] = Field(None, description="场景类型（可选）")
    session_id: Optional[str] = Field(None, description="会话ID（可选）")


def _get_missing_fields(checklist: Dict[str, Any], scenario_type: str) -> List[str]:
    scenario = ScenarioRegistry.get(scenario_type)
    if scenario:
        missing = []
        for field in scenario.p1_fields:
            key = field.get("key")
            if not key:
                continue
            if not checklist.get(key, False):
                missing.append(key)
        return missing
    return [key for key, done in checklist.items() if not done]


def _extract_next_question(messages: List[Dict[str, Any]]) -> Optional[str]:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return msg.get("content")
    return None


def _build_public_event(state: Dict[str, Any], session_id: str, *, node: str, status: str) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "node": node,
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "status": status,
        "fsm_state": state.get("fsm_state", "INIT"),
        "scenario_type": state.get("scenario_type", ""),
        "incident": state.get("incident", {}),
        "checklist": state.get("checklist", {}),
        "risk_assessment": state.get("risk_assessment", {}),
    }

    next_question = _extract_next_question(state.get("messages", []))
    if next_question:
        event["next_question"] = next_question

    return event


async def _stream_one_shot_execution(state: Dict[str, Any], session_id: str, session_store):
    try:
        config = get_agent_config()

        for chunk in agent.stream(state, config=config):
            for node_name, node_output in chunk.items():
                state.update(node_output)
                event_data = _build_public_event(state, session_id, node=node_name, status="processing")
                yield f"event: node_update\ndata: {json.dumps(event_data, ensure_ascii=False, default=str)}\n\n"
                await asyncio.sleep(0.05)

        recommendation = build_external_recommendation(state)
        final_event = _build_public_event(state, session_id, node="complete", status="completed")
        final_event["recommendation"] = recommendation

        yield f"event: complete\ndata: {json.dumps(final_event, ensure_ascii=False, default=str)}\n\n"

        await session_store.set(session_id, state, settings.SESSION_TTL_SECONDS)

    except Exception as exc:
        error_event = {
            "session_id": session_id,
            "status": "error",
            "error": str(exc),
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"


@router.post("/parse", response_model=AnalyzeParseResponse)
async def analyze_parse(
    request: AnalyzeParseRequest,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    scenario_type = request.scenario_type or identify_scenario(request.message)
    state = create_initial_state(
        session_id=f"analyze-parse-{uuid.uuid4().hex[:8]}",
        scenario_type=scenario_type,
        initial_message=request.message,
    )

    updates = input_parser_node(state)
    state.update(updates)

    scenario_type = state.get("scenario_type", scenario_type)
    checklist = state.get("checklist", {})

    return AnalyzeParseResponse(
        scenario_type=scenario_type,
        incident=state.get("incident", {}),
        checklist=checklist,
        missing_fields=_get_missing_fields(checklist, scenario_type),
    )


@router.post("/start/stream")
async def analyze_start_stream(
    request: AnalyzeStartRequest,
    req: Request,
    _user: str = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit_check),
):
    session_id = request.session_id or str(uuid.uuid4())

    session_store = getattr(req.app.state, "session_store", None)
    if session_store is None:
        raise HTTPException(status_code=500, detail="session_store not configured")

    await session_store.cleanup_expired()

    scenario_type = request.scenario_type or identify_scenario(request.message)

    state = create_initial_state(
        session_id=session_id,
        scenario_type=scenario_type,
        initial_message=request.message,
    )

    return StreamingResponse(
        _stream_one_shot_execution(state, session_id, session_store),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
