"""
工具输入验证测试

测试覆盖:
- 通用验证函数
- 各工具输入模式
- 验证框架集成
"""
import pytest
from pydantic import ValidationError

from tools.schemas import (
    # 验证函数
    sanitize_string,
    validate_position,
    validate_flight_number,
    validate_fluid_type,
    validate_risk_level,
    validate_leak_size,
    # 输入模式
    FlightPlanLookupInput,
    AskForDetailInput,
    CalculateImpactZoneInput,
    AssessRiskInput,
    NotifyDepartmentInput,
    PredictFlightImpactInput,
    GetWeatherInput,
    SearchRegulationsInput,
    GetAircraftInfoInput,
    AnalyzePositionImpactInput,
    AnalyzeSpillComprehensiveInput,
    AssessBirdStrikeRiskInput,
    AssessWeatherImpactInput,
    EstimateCleanupTimeInput,
    GenerateReportInput,
    GetStandLocationInput,
    SmartAskInput,
    AssessFodRiskInput,
    get_input_schema,
    INPUT_SCHEMAS,
)


class TestSanitizeString:
    """字符串清理测试"""

    def test_normal_string(self):
        """测试普通字符串"""
        assert sanitize_string("hello world") == "hello world"

    def test_remove_dangerous_chars(self):
        """测试移除危险字符"""
        assert sanitize_string("<script>alert()</script>") == "scriptalert()/script"

    def test_truncate_long_string(self):
        """测试截断过长字符串"""
        long_str = "a" * 2000
        result = sanitize_string(long_str, max_length=100)
        assert len(result) == 100

    def test_strip_whitespace(self):
        """测试去除首尾空白"""
        assert sanitize_string("  hello  ") == "hello"

    def test_non_string_raises(self):
        """测试非字符串抛出异常"""
        with pytest.raises(ValueError):
            sanitize_string(123)


class TestValidatePosition:
    """位置验证测试"""

    def test_numeric_position(self):
        """测试数字机位"""
        assert validate_position("501") == "501"
        assert validate_position("32") == "32"

    def test_alphanumeric_position(self):
        """测试字母数字混合机位"""
        assert validate_position("32L") == "32L"
        assert validate_position("W2") == "W2"
        assert validate_position("TWY_A3") == "TWY_A3"

    def test_normalize_spaces(self):
        """测试空格转下划线"""
        assert validate_position("TWY A3") == "TWY_A3"

    def test_uppercase_conversion(self):
        """测试转大写"""
        assert validate_position("runway_24r") == "RUNWAY_24R"

    def test_empty_raises(self):
        """测试空值抛出异常"""
        with pytest.raises(ValueError):
            validate_position("")

    def test_invalid_format_raises(self):
        """测试无效格式抛出异常"""
        with pytest.raises(ValueError):
            validate_position("位置@#$")


class TestValidateFlightNumber:
    """航班号验证测试"""

    def test_standard_format(self):
        """测试标准格式"""
        assert validate_flight_number("MU5678") == "MU5678"
        assert validate_flight_number("CA1234") == "CA1234"
        assert validate_flight_number("CES2876") == "CES2876"

    def test_with_suffix(self):
        """测试带后缀的航班号"""
        assert validate_flight_number("MU567A") == "MU567A"

    def test_normalize_case(self):
        """测试大小写规范化"""
        assert validate_flight_number("mu5678") == "MU5678"

    def test_remove_spaces(self):
        """测试移除空格"""
        assert validate_flight_number("MU 5678") == "MU5678"

    def test_empty_raises(self):
        """测试空值抛出异常"""
        with pytest.raises(ValueError):
            validate_flight_number("")

    def test_invalid_format_raises(self):
        """测试无效格式抛出异常"""
        with pytest.raises(ValueError):
            validate_flight_number("INVALID")

    def test_chinese_airline(self):
        """测试中文航司格式"""
        assert validate_flight_number("东航2392") == "东航2392"
        assert validate_flight_number("东航 2392") == "东航2392"


class TestValidateFluidType:
    """油液类型验证测试"""

    def test_valid_types(self):
        """测试有效类型"""
        assert validate_fluid_type("FUEL") == "FUEL"
        assert validate_fluid_type("HYDRAULIC") == "HYDRAULIC"
        assert validate_fluid_type("OIL") == "OIL"

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert validate_fluid_type("fuel") == "FUEL"
        assert validate_fluid_type("Hydraulic") == "HYDRAULIC"

    def test_invalid_type_raises(self):
        """测试无效类型抛出异常"""
        with pytest.raises(ValueError):
            validate_fluid_type("WATER")


class TestValidateRiskLevel:
    """风险等级验证测试"""

    def test_text_levels(self):
        """测试文本等级"""
        assert validate_risk_level("LOW") == "LOW"
        assert validate_risk_level("MEDIUM") == "MEDIUM"
        assert validate_risk_level("HIGH") == "HIGH"
        assert validate_risk_level("CRITICAL") == "CRITICAL"

    def test_r_levels(self):
        """测试 R 等级"""
        assert validate_risk_level("R1") == "R1"
        assert validate_risk_level("R4") == "R4"

    def test_invalid_level_raises(self):
        """测试无效等级抛出异常"""
        with pytest.raises(ValueError):
            validate_risk_level("UNKNOWN")


class TestValidateLeakSize:
    """泄漏面积验证测试"""

    def test_valid_sizes(self):
        """测试有效尺寸"""
        assert validate_leak_size("SMALL") == "SMALL"
        assert validate_leak_size("MEDIUM") == "MEDIUM"
        assert validate_leak_size("LARGE") == "LARGE"
        assert validate_leak_size("UNKNOWN") == "UNKNOWN"

    def test_invalid_size_raises(self):
        """测试无效尺寸抛出异常"""
        with pytest.raises(ValueError):
            validate_leak_size("HUGE")


class TestFlightPlanLookupInput:
    """航班计划查询输入测试"""

    def test_valid_input(self):
        """测试有效输入"""
        inp = FlightPlanLookupInput(flight_no="MU5678")
        assert inp.flight_no == "MU5678"

    def test_validation_applied(self):
        """测试验证被应用"""
        inp = FlightPlanLookupInput(flight_no="mu 5678")
        assert inp.flight_no == "MU5678"

    def test_invalid_raises(self):
        """测试无效输入抛出异常"""
        with pytest.raises(ValidationError):
            FlightPlanLookupInput(flight_no="")

    def test_chinese_flight_no(self):
        """测试中文航班号"""
        inp = FlightPlanLookupInput(flight_no="东航2392")
        assert inp.flight_no == "东航2392"


class TestGetAircraftInfoInput:
    """航班信息查询输入测试"""

    def test_chinese_flight_no(self):
        """测试中文航班号"""
        inp = GetAircraftInfoInput(flight_no="东航2392")
        assert inp.flight_no == "东航2392"


class TestAssessRiskInput:
    """风险评估输入测试"""

    def test_all_optional(self):
        """测试所有字段可选"""
        inp = AssessRiskInput()
        assert inp.fluid_type is None
        assert inp.leak_size is None

    def test_with_values(self):
        """测试带值创建"""
        inp = AssessRiskInput(fluid_type="fuel", leak_size="small")
        assert inp.fluid_type == "FUEL"
        assert inp.leak_size == "SMALL"

    def test_invalid_fluid_type(self):
        """测试无效油液类型"""
        with pytest.raises(ValidationError):
            AssessRiskInput(fluid_type="water")


class TestCalculateImpactZoneInput:
    """计算影响区域输入测试"""

    def test_valid_input(self):
        """测试有效输入"""
        inp = CalculateImpactZoneInput(position="501", fluid_type="fuel", risk_level="r3")
        assert inp.position == "501"
        assert inp.fluid_type == "FUEL"
        assert inp.risk_level == "R3"

    def test_all_optional(self):
        """测试字段可选"""
        inp = CalculateImpactZoneInput()
        assert inp.position is None
        assert inp.fluid_type is None
        assert inp.risk_level is None


class TestPredictFlightImpactInput:
    """航班影响预测输入测试"""

    def test_defaults(self):
        """测试默认值"""
        inp = PredictFlightImpactInput()
        assert inp.time_window == 2
        assert inp.use_cache is True

    def test_time_window_bounds(self):
        """测试时间窗口边界"""
        with pytest.raises(ValidationError):
            PredictFlightImpactInput(time_window=0)
        with pytest.raises(ValidationError):
            PredictFlightImpactInput(time_window=25)

    def test_optional_fields(self):
        """测试可选字段"""
        inp = PredictFlightImpactInput(flight_plan_file="/tmp/plan.json", use_cache=False)
        assert inp.flight_plan_file == "/tmp/plan.json"
        assert inp.use_cache is False


class TestGetWeatherInput:
    """气象查询输入测试"""

    def test_alias_mapping(self):
        """测试位置/时间兼容字段映射"""
        inp = GetWeatherInput(position="05L", time="2026-01-06 05:30:00")
        assert inp.location == "05L"
        assert inp.timestamp == "2026-01-06 05:30:00"


class TestSearchRegulationsInput:
    """规程检索输入测试"""

    def test_optional_fields(self):
        """测试可选字段"""
        inp = SearchRegulationsInput(query="燃油 泄漏", fluid_type="fuel", include_cases=False)
        assert inp.fluid_type == "FUEL"
        assert inp.include_cases is False


class TestNotifyDepartmentInput:
    """通知部门输入测试"""

    def test_valid_input(self):
        """测试有效输入"""
        inp = NotifyDepartmentInput(department="消防队")
        assert inp.department == "消防队"

    def test_with_message(self):
        """测试带消息"""
        inp = NotifyDepartmentInput(department="消防队", message="紧急情况")
        assert inp.message == "紧急情况"

    def test_with_priority(self):
        """测试优先级字段"""
        inp = NotifyDepartmentInput(department="消防队", priority="high")
        assert inp.priority == "high"

    def test_sanitize_applied(self):
        """测试清理被应用"""
        inp = NotifyDepartmentInput(department="<消防队>")
        assert "<" not in inp.department


class TestAssessBirdStrikeRiskInput:
    """鸟击风险评估输入测试"""

    def test_all_optional(self):
        """测试所有字段可选"""
        inp = AssessBirdStrikeRiskInput()
        assert inp.phase is None

    def test_alias_mapping(self):
        """测试兼容字段映射"""
        inp = AssessBirdStrikeRiskInput(flight_phase="takeoff")
        assert inp.phase == "takeoff"

        inp = AssessBirdStrikeRiskInput(impact_area="发动机")
        assert inp.affected_part == "发动机"

        inp = AssessBirdStrikeRiskInput(bird_size="大型鸟")
        assert inp.bird_info == "大型鸟"

    def test_damage_severity_mapping(self):
        """测试损伤程度映射到证据"""
        inp = AssessBirdStrikeRiskInput(damage_severity="minor")
        assert inp.evidence == "minor"


class TestAssessFodRiskInput:
    """FOD 风险评估输入测试"""

    def test_alias_mapping(self):
        """测试位置/尺寸兼容字段映射"""
        inp = AssessFodRiskInput(location="A1", size="LARGE")
        assert inp.position == "A1"
        assert inp.fod_size == "LARGE"


class TestGenerateReportInput:
    """生成报告输入测试"""

    def test_defaults(self):
        """测试默认值"""
        inp = GenerateReportInput()
        assert inp.include_recommendations is True
        assert inp.format == "checklist"

    def test_format_validation(self):
        """测试格式验证"""
        inp = GenerateReportInput(format="narrative")
        assert inp.format == "narrative"

        # 兼容格式映射
        inp = GenerateReportInput(format="summary")
        assert inp.format == "narrative"

        # 无效格式回退到默认
        inp = GenerateReportInput(format="invalid")
        assert inp.format == "checklist"


class TestGetInputSchema:
    """获取输入模式测试"""

    def test_registered_tools(self):
        """测试已注册工具"""
        assert get_input_schema("flight_plan_lookup") == FlightPlanLookupInput
        assert get_input_schema("assess_risk") == AssessRiskInput
        assert get_input_schema("notify_department") == NotifyDepartmentInput

    def test_unregistered_tool(self):
        """测试未注册工具"""
        assert get_input_schema("unknown_tool") is None

    def test_schema_coverage(self):
        """测试 schema 覆盖率"""
        expected_tools = {
            "flight_plan_lookup",
            "get_aircraft_info",
            "ask_for_detail",
            "get_weather",
            "smart_ask",
            "calculate_impact_zone",
            "predict_flight_impact",
            "analyze_position_impact",
            "get_stand_location",
            "assess_risk",
            "assess_oil_spill_risk",
            "assess_bird_strike_risk",
            "assess_weather_impact",
            "assess_fod_risk",
            "estimate_cleanup_time",
            "analyze_spill_comprehensive",
            "notify_department",
            "generate_report",
            "search_regulations",
        }
        assert set(INPUT_SCHEMAS.keys()) == expected_tools


class TestToolValidationIntegration:
    """工具验证集成测试"""

    def test_execute_with_validation_valid_input(self):
        """测试有效输入的验证执行"""
        from tools.base import BaseTool

        class MockTool(BaseTool):
            name = "flight_plan_lookup"
            description = "Mock tool"

            def execute(self, state, inputs):
                return {"observation": f"Looked up {inputs['flight_no']}"}

        tool = MockTool()
        result = tool.execute_with_validation({}, {"flight_no": "mu5678"})

        assert "observation" in result
        assert "MU5678" in result["observation"]

    def test_execute_with_validation_invalid_input(self):
        """测试无效输入的验证执行"""
        from tools.base import BaseTool

        class MockTool(BaseTool):
            name = "flight_plan_lookup"
            description = "Mock tool"

            def execute(self, state, inputs):
                return {"observation": "Should not reach here"}

        tool = MockTool()
        result = tool.execute_with_validation({}, {"flight_no": ""})

        assert "error" in result or "无效" in result.get("observation", "")

    def test_execute_with_validation_disabled(self):
        """测试禁用验证时的执行"""
        from tools.base import BaseTool

        class MockTool(BaseTool):
            name = "flight_plan_lookup"
            description = "Mock tool"
            enable_validation = False

            def execute(self, state, inputs):
                return {"observation": f"Raw input: {inputs}"}

        tool = MockTool()
        # 即使输入无效，禁用验证时也应该直接执行
        result = tool.execute_with_validation({}, {"flight_no": ""})
        assert "Raw input" in result["observation"]

    def test_execute_with_validation_aliases(self):
        """测试真实工具的字段映射"""
        from tools.information.get_weather import GetWeatherTool

        tool = GetWeatherTool()
        result = tool.execute_with_validation({"incident": {"position": "05L"}}, {"position": "05L"})

        assert "observation" in result
        assert "请提供位置" not in result["observation"]
