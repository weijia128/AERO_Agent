"""
工具输入/输出验证模式

定义通用验证器和各工具的输入模式。
"""
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# =============================================================================
# 基础验证类
# =============================================================================


class ToolInput(BaseModel):
    """工具输入基类"""
    model_config = ConfigDict(extra="ignore")  # 忽略额外字段，提高容错性


class ToolOutput(BaseModel):
    """工具输出基类"""

    observation: str = Field(..., description="工具执行结果描述")
    success: bool = Field(default=True, description="是否执行成功")
    error: Optional[str] = Field(default=None, description="错误信息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="结构化数据")


# =============================================================================
# 通用验证函数
# =============================================================================


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    清理字符串输入

    Args:
        value: 输入字符串
        max_length: 最大长度

    Returns:
        清理后的字符串
    """
    if not isinstance(value, str):
        raise ValueError("必须是字符串")

    # 移除潜在危险字符（防止注入）
    value = re.sub(r"[<>]", "", value)

    # 截断过长输入
    if len(value) > max_length:
        value = value[:max_length]

    return value.strip()


def validate_position(value: str) -> str:
    """
    验证机位/位置格式

    Args:
        value: 位置字符串

    Returns:
        规范化的位置字符串
    """
    if not value:
        raise ValueError("位置不能为空")

    # 允许的格式: 数字、字母+数字、滑行道名称等
    # 501, 32L, TWY_A3, runway_24R, W2
    pattern = r"^[A-Za-z0-9_\-]{1,30}$"
    normalized = value.strip().replace(" ", "_")

    if not re.match(pattern, normalized):
        raise ValueError(f"位置格式无效: {value}")

    return normalized.upper()


def validate_flight_number(value: str) -> str:
    """
    验证航班号格式

    Args:
        value: 航班号字符串

    Returns:
        规范化的航班号
    """
    if not value:
        raise ValueError("航班号不能为空")

    raw = value.strip()

    # 兼容中文航司前缀（如 东航2392）
    if re.search(r"[\u4e00-\u9fff]", raw):
        compact = re.sub(r"\s+", "", raw)
        if re.match(r"^[\u4e00-\u9fff]{1,6}\d{2,5}[A-Z]?$", compact):
            return compact

    # 移除空格并转大写
    normalized = raw.upper().replace(" ", "")

    # 标准航班号格式: 2-3字母 + 1-4数字 + 可选后缀字母
    pattern = r"^[A-Z]{2,3}\d{1,4}[A-Z]?$"

    if not re.match(pattern, normalized):
        # 尝试兼容其他格式
        # CES2876, MU5678 等
        alt_pattern = r"^[A-Z]{2,4}\d{2,5}$"
        if not re.match(alt_pattern, normalized):
            raise ValueError(f"航班号格式无效: {value}")

    return normalized


def validate_fluid_type(value: str) -> str:
    """
    验证油液类型

    Args:
        value: 油液类型字符串

    Returns:
        规范化的油液类型
    """
    allowed = {"FUEL", "HYDRAULIC", "OIL"}
    normalized = value.upper().strip()

    if normalized not in allowed:
        raise ValueError(f"油液类型必须是: {allowed}")

    return normalized


def validate_risk_level(value: str) -> str:
    """
    验证风险等级

    Args:
        value: 风险等级字符串

    Returns:
        规范化的风险等级
    """
    allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "R1", "R2", "R3", "R4"}
    normalized = value.upper().strip()

    if normalized not in allowed:
        raise ValueError(f"风险等级必须是: {allowed}")

    return normalized


def validate_leak_size(value: str) -> str:
    """
    验证泄漏面积

    Args:
        value: 泄漏面积字符串

    Returns:
        规范化的泄漏面积
    """
    allowed = {"SMALL", "MEDIUM", "LARGE", "UNKNOWN"}
    normalized = value.upper().strip()

    if normalized not in allowed:
        raise ValueError(f"泄漏面积必须是: {allowed}")

    return normalized


# =============================================================================
# 具体工具输入模式
# =============================================================================


class FlightPlanLookupInput(ToolInput):
    """航班计划查询输入"""

    flight_no: str = Field(..., description="航班号", min_length=3, max_length=10)

    @field_validator("flight_no")
    @classmethod
    def validate_flight_no(cls, v: str) -> str:
        return validate_flight_number(v)


class AskForDetailInput(ToolInput):
    """询问详情输入"""

    question: Optional[str] = Field(None, description="问题内容", max_length=500)
    field: Optional[str] = Field(None, description="字段名称", max_length=100)

    @field_validator("question", "field", mode="before")
    @classmethod
    def sanitize(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=500)


class CalculateImpactZoneInput(ToolInput):
    """计算影响区域输入"""

    position: Optional[str] = Field(None, description="事故位置")
    fluid_type: Optional[str] = Field(None, description="油液类型")
    risk_level: Optional[str] = Field(None, description="风险等级")

    @field_validator("position", mode="before")
    @classmethod
    def validate_pos(cls, v):
        if v is None:
            return v
        return validate_position(v)

    @field_validator("fluid_type", mode="before")
    @classmethod
    def validate_fluid(cls, v):
        if v is None:
            return v
        return validate_fluid_type(v)

    @field_validator("risk_level", mode="before")
    @classmethod
    def validate_risk(cls, v):
        if v is None:
            return v
        return validate_risk_level(v)


class AssessRiskInput(ToolInput):
    """风险评估输入"""

    fluid_type: Optional[str] = Field(None, description="油液类型")
    leak_size: Optional[str] = Field(None, description="泄漏面积")
    engine_status: Optional[str] = Field(None, description="发动机状态")
    continuous: Optional[bool] = Field(None, description="是否持续泄漏")

    @field_validator("fluid_type", mode="before")
    @classmethod
    def validate_fluid(cls, v):
        if v is None:
            return v
        return validate_fluid_type(v)

    @field_validator("leak_size", mode="before")
    @classmethod
    def validate_size(cls, v):
        if v is None:
            return v
        return validate_leak_size(v)


class NotifyDepartmentInput(ToolInput):
    """通知部门输入"""

    department: str = Field(..., description="部门名称", min_length=1, max_length=50)
    message: Optional[str] = Field(None, description="通知内容", max_length=500)
    priority: Optional[str] = Field(None, description="优先级")

    @field_validator("department", "message", "priority", mode="before")
    @classmethod
    def sanitize(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=500)


class PredictFlightImpactInput(ToolInput):
    """航班影响预测输入"""

    time_window: Optional[int] = Field(
        default=2, description="预测时间窗口(小时)", ge=1, le=24
    )
    affected_stands: Optional[List[str]] = Field(None, description="受影响机位列表")
    affected_runways: Optional[List[str]] = Field(None, description="受影响跑道列表")
    flight_plan_file: Optional[str] = Field(None, description="航班计划文件路径")
    use_cache: Optional[bool] = Field(default=True, description="是否使用缓存数据")

    @field_validator("flight_plan_file", mode="before")
    @classmethod
    def sanitize_path(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=300)


class GetWeatherInput(ToolInput):
    """获取天气输入"""

    location: Optional[str] = Field(None, description="位置")
    timestamp: Optional[str] = Field(None, description="时间戳")
    position: Optional[str] = Field(None, description="位置(兼容字段)")
    time: Optional[str] = Field(None, description="时间(兼容字段)")

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values):
        if not isinstance(values, dict):
            return values
        if not values.get("location") and values.get("position"):
            values["location"] = values.get("position")
        if not values.get("timestamp") and values.get("time"):
            values["timestamp"] = values.get("time")
        return values

    @field_validator("location", "position", mode="before")
    @classmethod
    def sanitize_location(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=50)

    @field_validator("timestamp", "time", mode="before")
    @classmethod
    def sanitize_timestamp(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=32)


class SearchRegulationsInput(ToolInput):
    """搜索规程输入"""

    query: str = Field(..., description="搜索关键词", min_length=2, max_length=200)
    fluid_type: Optional[str] = Field(None, description="油液类型")
    include_cases: Optional[bool] = Field(default=True, description="是否包含历史案例")

    @field_validator("query")
    @classmethod
    def sanitize(cls, v: str) -> str:
        return sanitize_string(v, max_length=200)

    @field_validator("fluid_type", mode="before")
    @classmethod
    def validate_fluid(cls, v):
        if v is None:
            return v
        return validate_fluid_type(v)


class GetAircraftInfoInput(ToolInput):
    """航班信息查询输入"""

    flight_no: str = Field(..., description="航班号", min_length=2, max_length=15)

    @field_validator("flight_no")
    @classmethod
    def validate_flight_no(cls, v: str) -> str:
        return validate_flight_number(v)


class AnalyzePositionImpactInput(ToolInput):
    """位置影响分析输入"""

    position: Optional[str] = Field(None, description="事故位置")
    fluid_type: Optional[str] = Field(None, description="油液类型")
    risk_level: Optional[str] = Field(None, description="风险等级")

    @field_validator("position", mode="before")
    @classmethod
    def validate_pos(cls, v):
        if v is None:
            return v
        return validate_position(v)

    @field_validator("fluid_type", mode="before")
    @classmethod
    def validate_fluid(cls, v):
        if v is None:
            return v
        return validate_fluid_type(v)

    @field_validator("risk_level", mode="before")
    @classmethod
    def validate_risk(cls, v):
        if v is None:
            return v
        return validate_risk_level(v)


class AnalyzeSpillComprehensiveInput(ToolInput):
    """漏油综合分析输入（主要从 state 读取，inputs 为可选覆盖）"""

    position: Optional[str] = Field(None, description="事故位置")
    fluid_type: Optional[str] = Field(None, description="油液类型")
    leak_size: Optional[str] = Field(None, description="泄漏面积")

    @field_validator("position", mode="before")
    @classmethod
    def validate_pos(cls, v):
        if v is None:
            return v
        return validate_position(v)

    @field_validator("fluid_type", mode="before")
    @classmethod
    def validate_fluid(cls, v):
        if v is None:
            return v
        return validate_fluid_type(v)

    @field_validator("leak_size", mode="before")
    @classmethod
    def validate_size(cls, v):
        if v is None:
            return v
        return validate_leak_size(v)


class AssessBirdStrikeRiskInput(ToolInput):
    """鸟击风险评估输入"""

    phase: Optional[str] = Field(None, description="飞行阶段")
    affected_part: Optional[str] = Field(None, description="受损部位")
    evidence: Optional[str] = Field(None, description="迹象强度")
    bird_info: Optional[str] = Field(None, description="鸟类信息")
    ops_impact: Optional[str] = Field(None, description="运行影响")
    impact_area: Optional[str] = Field(None, description="撞击部位(兼容字段)")
    flight_phase: Optional[str] = Field(None, description="飞行阶段(兼容字段)")
    damage_severity: Optional[str] = Field(None, description="损伤程度(兼容字段)")
    bird_size: Optional[str] = Field(None, description="鸟类大小(兼容字段)")

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values):
        if not isinstance(values, dict):
            return values
        if not values.get("phase") and values.get("flight_phase"):
            values["phase"] = values.get("flight_phase")
        if not values.get("affected_part") and values.get("impact_area"):
            values["affected_part"] = values.get("impact_area")
        if not values.get("evidence") and values.get("damage_severity"):
            values["evidence"] = values.get("damage_severity")
        if not values.get("bird_info") and values.get("bird_size"):
            values["bird_info"] = values.get("bird_size")
        return values

    @field_validator(
        "phase",
        "affected_part",
        "evidence",
        "bird_info",
        "ops_impact",
        "impact_area",
        "flight_phase",
        "damage_severity",
        "bird_size",
        mode="before",
    )
    @classmethod
    def sanitize_fields(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=100)


class AssessWeatherImpactInput(ToolInput):
    """气象影响评估输入"""

    fluid_type: Optional[str] = Field(None, description="油液类型")
    leak_size: Optional[str] = Field(None, description="泄漏面积")
    position: Optional[str] = Field(None, description="位置")

    @field_validator("fluid_type", mode="before")
    @classmethod
    def validate_fluid(cls, v):
        if v is None:
            return v
        return validate_fluid_type(v)

    @field_validator("leak_size", mode="before")
    @classmethod
    def validate_size(cls, v):
        if v is None:
            return v
        return validate_leak_size(v)


class EstimateCleanupTimeInput(ToolInput):
    """清理时间预估输入"""

    fluid_type: Optional[str] = Field(None, description="油液类型")
    leak_size: Optional[str] = Field(None, description="泄漏面积")
    position: Optional[str] = Field(None, description="位置")

    @field_validator("fluid_type", mode="before")
    @classmethod
    def validate_fluid(cls, v):
        if v is None:
            return v
        return validate_fluid_type(v)

    @field_validator("leak_size", mode="before")
    @classmethod
    def validate_size(cls, v):
        if v is None:
            return v
        return validate_leak_size(v)


class GenerateReportInput(ToolInput):
    """生成报告输入"""

    include_recommendations: Optional[bool] = Field(True, description="是否包含建议")
    format: Optional[str] = Field("checklist", description="报告格式")

    @field_validator("format", mode="before")
    @classmethod
    def validate_format(cls, v):
        if v is None:
            return "checklist"
        allowed = {"checklist", "narrative"}
        normalized = str(v).lower().strip()
        if normalized in {"summary", "detailed"}:
            return "narrative"
        if normalized not in allowed:
            return "checklist"
        return normalized


class GetStandLocationInput(ToolInput):
    """获取机位位置输入"""

    stand_id: Optional[str] = Field(None, description="机位编号")
    taxiway: Optional[str] = Field(None, description="滑行道编号")

    @field_validator("stand_id", "taxiway", mode="before")
    @classmethod
    def validate_id(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=30)


class SmartAskInput(ToolInput):
    """智能问询输入"""

    missing_fields: Optional[List[str]] = Field(None, description="缺失字段列表")
    scenario_type: Optional[str] = Field(None, description="场景类型")


class AssessFodRiskInput(ToolInput):
    """FOD 风险评估输入"""

    location_area: Optional[str] = Field(None, description="发现区域")
    position: Optional[str] = Field(None, description="发现位置")
    fod_type: Optional[str] = Field(None, description="FOD 类型")
    presence: Optional[str] = Field(None, description="FOD 状态")
    fod_size: Optional[str] = Field(None, description="FOD 大小")
    impact_note: Optional[str] = Field(None, description="影响备注")
    location_segment: Optional[str] = Field(None, description="位置段位")
    centerline_offset_m: Optional[float] = Field(None, description="距中线偏移(米)")
    report_time: Optional[str] = Field(None, description="报告时间")
    location: Optional[str] = Field(None, description="发现位置(兼容字段)")
    size: Optional[str] = Field(None, description="FOD 大小(兼容字段)")

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values):
        if not isinstance(values, dict):
            return values
        if not values.get("position") and values.get("location"):
            values["position"] = values.get("location")
        if not values.get("fod_size") and values.get("size"):
            values["fod_size"] = values.get("size")
        return values

    @field_validator(
        "location_area",
        "position",
        "fod_type",
        "presence",
        "fod_size",
        "impact_note",
        "location_segment",
        "report_time",
        "location",
        "size",
        mode="before",
    )
    @classmethod
    def sanitize_fields(cls, v):
        if v is None:
            return v
        return sanitize_string(str(v), max_length=200)

    @field_validator("centerline_offset_m", mode="before")
    @classmethod
    def normalize_offset(cls, v):
        if v is None:
            return v
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


# =============================================================================
# 输入模式注册表
# =============================================================================

INPUT_SCHEMAS = {
    # 信息查询工具
    "flight_plan_lookup": FlightPlanLookupInput,
    "get_aircraft_info": GetAircraftInfoInput,
    "ask_for_detail": AskForDetailInput,
    "get_weather": GetWeatherInput,
    "smart_ask": SmartAskInput,
    # 空间分析工具
    "calculate_impact_zone": CalculateImpactZoneInput,
    "predict_flight_impact": PredictFlightImpactInput,
    "analyze_position_impact": AnalyzePositionImpactInput,
    "get_stand_location": GetStandLocationInput,
    # 评估工具
    "assess_risk": AssessRiskInput,
    "assess_oil_spill_risk": AssessRiskInput,
    "assess_bird_strike_risk": AssessBirdStrikeRiskInput,
    "assess_weather_impact": AssessWeatherImpactInput,
    "assess_fod_risk": AssessFodRiskInput,
    "estimate_cleanup_time": EstimateCleanupTimeInput,
    "analyze_spill_comprehensive": AnalyzeSpillComprehensiveInput,
    # 动作工具
    "notify_department": NotifyDepartmentInput,
    "generate_report": GenerateReportInput,
    # 知识库工具
    "search_regulations": SearchRegulationsInput,
}


def get_input_schema(tool_name: str):
    """
    获取工具的输入验证模式

    Args:
        tool_name: 工具名称

    Returns:
        对应的输入模式类，如果不存在则返回 None
    """
    return INPUT_SCHEMAS.get(tool_name)
