"""
Core type definitions for agent state.
"""
from typing import Any, Dict, List, Literal, Optional, TypedDict


class IncidentInfoData(TypedDict, total=False):
    scenario: str
    position: str
    fluid_type: Optional[str]
    leak_size: Optional[str]
    incident_time: Optional[str]
    flight_no: Optional[str]
    aircraft_type: Optional[str]
    engine_status: Optional[str]
    continuous: Optional[bool]
    reported_by: Optional[str]
    report_time: Optional[str]


class RiskAssessmentData(TypedDict, total=False):
    level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "R1", "R2", "R3", "R4", "UNKNOWN"]
    score: int
    factors: List[str]
    immediate_actions: List[str]
    rationale: str
    assessed_at: Optional[str]


class SpatialAnalysisData(TypedDict, total=False):
    affected_stands: List[str]
    affected_taxiways: List[str]
    affected_runways: List[str]
    impact_radius: int
    anchor_node: Optional[str]
    isolated_nodes: List[str]
    affected_flights: Dict[str, str]


class FlightImpactData(TypedDict, total=False):
    time_window: Dict[str, str]
    affected_flights: List[Dict[str, Any]]
    statistics: Dict[str, Any]


class AgentStateData(TypedDict, total=False):
    session_id: str
    scenario_type: str
    created_at: str
    incident: IncidentInfoData
    checklist: Dict[str, bool]
    risk_assessment: RiskAssessmentData
    spatial_analysis: SpatialAnalysisData
    flight_impact: FlightImpactData
    reference_flight: Dict[str, Any]
    fsm_state: str
    messages: List[Dict[str, str]]
    next_action: Optional[str]
    action_input: Optional[Dict[str, Any]]
    tool_result: Optional[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]
    final_answer: Optional[str]
