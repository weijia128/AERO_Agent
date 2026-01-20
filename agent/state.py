"""
Agent 状态定义

融合方案核心：
1. 统一状态管理（来自 ReAct 方案）
2. FSM 状态追踪（来自文档方案）
3. Checklist 约束状态（来自文档方案）
"""
from typing import TypedDict, Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================
# 枚举定义
# ============================================================

class RiskLevel(str, Enum):
    """风险等级"""
    R4 = "R4"
    R3 = "R3"
    R2 = "R2"
    R1 = "R1"
    UNKNOWN = "UNKNOWN"


RISK_LEVEL_ALIASES = {
    "HIGH": RiskLevel.R3.value,
    "MEDIUM_HIGH": RiskLevel.R3.value,
    "MEDIUM": RiskLevel.R2.value,
    "LOW": RiskLevel.R1.value,
}


def normalize_risk_level(level: str) -> str:
    """将历史风险等级映射为 R1-R4。"""
    if not level:
        return RiskLevel.UNKNOWN.value
    upper = str(level).strip().upper()
    if upper in {RiskLevel.R1.value, RiskLevel.R2.value, RiskLevel.R3.value, RiskLevel.R4.value}:
        return upper
    return RISK_LEVEL_ALIASES.get(upper, level)


def risk_level_rank(level: str) -> int:
    """返回风险等级强度排序（0=最低/未知）。"""
    normalized = normalize_risk_level(level)
    return {
        RiskLevel.R1.value: 1,
        RiskLevel.R2.value: 2,
        RiskLevel.R3.value: 3,
        RiskLevel.R4.value: 4,
    }.get(normalized, 0)


class FSMState(str, Enum):
    """FSM 状态（来自文档方案）"""
    INIT = "INIT"                          # 初始状态
    P1_RISK_ASSESS = "P1_RISK_ASSESS"      # 风险评估
    P2_IMMEDIATE_CONTROL = "P2_IMMEDIATE_CONTROL"  # 立即控制
    P3_RESOURCE_DISPATCH = "P3_RESOURCE_DISPATCH"  # 资源调度
    P4_AREA_ISOLATION = "P4_AREA_ISOLATION"        # 区域隔离
    P5_CLEANUP = "P5_CLEANUP"              # 清污执行
    P6_VERIFICATION = "P6_VERIFICATION"    # 结果确认
    P7_RECOVERY = "P7_RECOVERY"            # 区域恢复
    P8_CLOSE = "P8_CLOSE"                  # 关闭与报告
    COMPLETED = "COMPLETED"                # 完成


class ActionStatus(str, Enum):
    """动作执行状态"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ============================================================
# Pydantic 模型（用于结构化数据）
# ============================================================

class IncidentInfo(BaseModel):
    """事件信息（对应文档方案的 FuelLeakState）"""
    # P1 优先级字段（必须收集）
    fluid_type: Optional[str] = Field(None, description="油液类型: FUEL/HYDRAULIC/OIL")
    continuous: Optional[bool] = Field(None, description="是否持续滴漏")
    engine_status: Optional[str] = Field(None, description="发动机状态: RUNNING/STOPPED")
    position: Optional[str] = Field(None, description="位置: 停机位/滑行道")
    
    # P2 优先级字段
    leak_size: Optional[str] = Field(None, description="面积: SMALL/MEDIUM/LARGE")

    # 附加信息
    flight_no: Optional[str] = Field(None, description="航班号(ICAO格式,用于内部处理)")
    flight_no_display: Optional[str] = Field(None, description="航班号(原始格式,用于对话显示)")
    reported_by: Optional[str] = Field(None, description="报告人")
    report_time: Optional[datetime] = Field(None, description="报告时间")


class ChecklistStatus(BaseModel):
    """Checklist 状态（来自文档方案）"""
    # P1 字段收集状态
    fluid_type_collected: bool = False
    continuous_collected: bool = False
    engine_status_collected: bool = False
    position_collected: bool = False
    
    # P2 字段收集状态
    leak_size_collected: bool = False
    
    @property
    def p1_complete(self) -> bool:
        """P1 字段是否全部收集"""
        return all([
            self.fluid_type_collected,
            self.continuous_collected,
            self.engine_status_collected,
            self.position_collected,
        ])
    
    @property
    def all_complete(self) -> bool:
        """所有字段是否全部收集"""
        return self.p1_complete and self.leak_size_collected


class RiskAssessment(BaseModel):
    """风险评估结果"""
    level: RiskLevel = RiskLevel.UNKNOWN
    score: int = 0
    factors: List[str] = Field(default_factory=list)
    immediate_actions: List[str] = Field(default_factory=list)
    rationale: str = ""
    assessed_at: Optional[datetime] = None


class SpatialAnalysis(BaseModel):
    """空间分析结果（对应文档方案的 AreaIsolationResult）"""
    anchor_node: Optional[str] = None  # 起始节点
    isolated_nodes: List[str] = Field(default_factory=list)  # 隔离节点
    affected_taxiways: List[str] = Field(default_factory=list)  # 受影响滑行道
    affected_runways: List[str] = Field(default_factory=list)  # 受影响跑道
    affected_flights: Dict[str, str] = Field(default_factory=dict)  # 受影响航班
    impact_radius: float = 0  # 影响半径(米)


class ReasoningStep(BaseModel):
    """推理步骤记录"""
    step: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ActionRecord(BaseModel):
    """执行动作记录"""
    action: str
    target: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    status: ActionStatus = ActionStatus.PENDING
    result: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class FSMTransition(BaseModel):
    """FSM 状态转换记录"""
    from_state: FSMState
    to_state: FSMState
    trigger: str  # 触发原因
    timestamp: datetime = Field(default_factory=datetime.now)


class FinalReport(BaseModel):
    """最终报告"""
    title: str = ""
    event_summary: str = ""
    risk_level: str = ""
    handling_process: List[str] = Field(default_factory=list)
    checklist_items: List[Dict[str, Any]] = Field(default_factory=list)
    coordination_units: List[str] = Field(default_factory=list)
    operational_impact: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


# ============================================================
# LangGraph State（TypedDict）
# ============================================================

class AgentState(TypedDict, total=False):
    """
    Agent 状态定义
    
    融合设计：
    - 保持 ReAct 的灵活状态管理
    - 加入 FSM 状态追踪（验证用）
    - 加入 Checklist 状态（约束用）
    """
    
    # ===== 基础信息 =====
    session_id: str                    # 会话 ID
    scenario_type: str                 # 场景类型
    created_at: str                    # 创建时间
    
    # ===== 事件信息 =====
    incident: Dict[str, Any]           # 事件信息（IncidentInfo）
    
    # ===== 对话历史 =====
    messages: List[Dict[str, str]]     # 对话消息
    
    # ===== ReAct 推理过程 =====
    reasoning_steps: List[Dict[str, Any]]  # 推理步骤
    current_thought: str               # 当前思考
    current_action: str                # 当前动作
    current_action_input: Dict[str, Any]  # 当前动作输入
    current_observation: str           # 当前观察
    
    # ===== Checklist 状态（来自文档方案）=====
    checklist: Dict[str, bool]         # Checklist 收集状态
    
    # ===== FSM 状态（来自文档方案，用于验证）=====
    fsm_state: str                     # 当前 FSM 状态
    fsm_history: List[Dict[str, Any]]  # FSM 转换历史
    fsm_validation_errors: List[str]   # FSM 验证错误
    
    # ===== 分析结果 =====
    risk_assessment: Dict[str, Any]    # 风险评估结果
    spatial_analysis: Dict[str, Any]   # 空间分析结果
    retrieved_knowledge: Dict[str, Any]  # 检索到的知识
    
    # ===== 约束状态 =====
    mandatory_actions_done: Dict[str, bool]  # 强制动作完成状态

    # ===== 语义理解与验证 =====
    semantic_understanding: Dict[str, Any]  # 语义理解结果
    semantic_validation: Dict[str, Any]     # 语义验证结果
    
    # ===== 执行记录 =====
    actions_taken: List[Dict[str, Any]]  # 已执行动作
    notifications_sent: List[Dict[str, Any]]  # 已发送通知
    
    # ===== 控制状态 =====
    current_node: str                  # 当前节点
    next_node: str                     # 下一节点
    iteration_count: int               # 迭代次数
    is_complete: bool                  # 是否完成
    report_generated: bool             # 报告是否已生成（等待用户确认）
    awaiting_user: bool               # 是否等待用户输入
    awaiting_supplemental_info: bool  # 是否等待补充信息
    supplemental_notes: List[str]     # 补充信息（原文）
    finalize_report: bool             # 是否需要重新生成报告
    supplemental_prompted: bool       # 是否已提示补充信息
    comprehensive_analysis_failed: bool  # 综合分析失败标记
    error: str                         # 错误信息
    
    # ===== 最终输出 =====
    final_report: Dict[str, Any]       # 最终报告
    final_answer: str                  # 最终回答


def create_initial_state(
    session_id: str,
    scenario_type: str = "oil_spill",
    initial_message: str = "",
) -> AgentState:
    """创建初始状态（从配置加载）"""
    from scenarios.base import ScenarioRegistry

    now = datetime.now().isoformat()

    # 从配置加载 checklist 字段
    scenario = ScenarioRegistry.get(scenario_type)
    incident_fields = {}
    checklist_fields = {}

    if scenario:
        # 初始化事件字段
        for field in scenario.p1_fields + scenario.p2_fields:
            key = field.get("key")
            if key:
                incident_fields[key] = None
                checklist_fields[key] = False
        # 添加报告时间
        incident_fields["report_time"] = now

        # 初始化强制动作
        mandatory_actions = {
            "risk_assessed": False,
            "fire_dept_notified": False,
            "atc_notified": False,
            "maintenance_notified": False,
            "cleaning_notified": False,
        }
    else:
        # 回退到默认值
        incident_fields = {
            "fluid_type": None,
            "continuous": None,
            "engine_status": None,
            "position": None,
            "leak_size": None,
            "flight_no": None,
            "reported_by": None,
            "report_time": now,
        }
        checklist_fields = {
            "fluid_type": False,
            "continuous": False,
            "engine_status": False,
            "position": False,
            "leak_size": False,
            "flight_no": False,  # 添加航班号到 checklist
        }
        mandatory_actions = {
            "risk_assessed": False,
            "fire_dept_notified": False,
            "atc_notified": False,
            "maintenance_notified": False,
            "cleaning_notified": False,
        }

    return AgentState(
        # 基础信息
        session_id=session_id,
        scenario_type=scenario_type,
        created_at=now,

        # 事件信息
        incident=incident_fields,

        # 对话历史
        messages=[{"role": "user", "content": initial_message}] if initial_message else [],

        # ReAct 推理过程
        reasoning_steps=[],
        current_thought="",
        current_action="",
        current_action_input={},
        current_observation="",

        # Checklist 状态（从配置加载）
        checklist=checklist_fields,

        # FSM 状态
        fsm_state=FSMState.INIT.value,
        fsm_history=[],
        fsm_validation_errors=[],

        # 分析结果
        risk_assessment={},
        spatial_analysis={},
        retrieved_knowledge={},

        # 约束状态（从配置加载）
        mandatory_actions_done=mandatory_actions,

        # 执行记录
        actions_taken=[],
        notifications_sent=[],

        # 控制状态
        current_node="input_parser",
        next_node="",
        iteration_count=0,
        is_complete=False,
        report_generated=False,
        awaiting_user=False,
        awaiting_supplemental_info=False,
        supplemental_notes=[],
        finalize_report=False,
        supplemental_prompted=False,
        comprehensive_analysis_failed=False,
        error="",

        # 最终输出
        final_report={},
        final_answer="",
        semantic_understanding={},
        semantic_validation={},
    )
