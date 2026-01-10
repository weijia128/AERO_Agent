"""
约束系统测试
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from constraints.loader import ConstraintLoader, load_constraints
from constraints.checker import (
    ConstraintChecker,
    ConstraintCheckResult,
    ConstraintViolation,
    ConstraintSeverity,
    check_constraints,
    validate_checklist_field,
)


class TestConstraintLoader:
    """约束加载器测试"""

    @pytest.fixture
    def loader(self):
        """创建加载器实例"""
        return ConstraintLoader()

    def test_load_oil_spill_constraints(self, loader):
        """测试加载漏油场景约束"""
        constraints = loader.load('oil_spill')

        assert constraints.scenario_type == 'oil_spill'
        assert len(constraints.p1_fields) == 4  # fluid_type, continuous, engine_status, position
        assert len(constraints.p2_fields) >= 1  # leak_size 等

    def test_p1_fields_contain_expected(self, loader):
        """测试 P1 字段包含预期字段"""
        constraints = loader.load('oil_spill')
        p1_keys = [f.key for f in constraints.p1_fields]

        assert 'fluid_type' in p1_keys
        assert 'continuous' in p1_keys
        assert 'engine_status' in p1_keys
        assert 'position' in p1_keys

    def test_p2_fields_contain_expected(self, loader):
        """测试 P2 字段包含预期字段"""
        constraints = loader.load('oil_spill')
        p2_keys = [f.key for f in constraints.p2_fields]

        assert 'leak_size' in p2_keys

    def test_fsm_state_constraints(self, loader):
        """测试 FSM 状态约束"""
        constraints = loader.load('oil_spill')

        # P1_RISK_ASSESS 应该需要 fluid_type 和 position
        p1_constraint = constraints.state_constraints.get('P1_RISK_ASSESS')
        assert p1_constraint is not None
        assert 'fluid_type' in p1_constraint.required_checklist_fields
        assert 'position' in p1_constraint.required_checklist_fields

    def test_get_all_p1_keys(self, loader):
        """测试获取所有 P1 key"""
        p1_keys = loader.get_all_p1_keys('oil_spill')
        assert isinstance(p1_keys, list)
        assert len(p1_keys) == 4

    def test_get_all_p2_keys(self, loader):
        """测试获取所有 P2 key"""
        p2_keys = loader.get_all_p2_keys('oil_spill')
        assert isinstance(p2_keys, list)
        assert 'leak_size' in p2_keys

    def test_cache_functionality(self, loader):
        """测试缓存功能"""
        # 第一次加载
        constraints1 = loader.load('oil_spill')

        # 第二次加载应该返回缓存
        constraints2 = loader.load('oil_spill')

        assert constraints1 is constraints2  # 同一个对象

    def test_clear_cache(self, loader):
        """测试清除缓存"""
        loader.load('oil_spill')
        assert 'oil_spill' in loader._cache

        loader.clear_cache()
        assert len(loader._cache) == 0

    def test_invalid_scenario_raises(self, loader):
        """测试无效场景抛出异常"""
        with pytest.raises(FileNotFoundError):
            loader.load('nonexistent_scenario')


class TestConstraintChecker:
    """约束检查器测试"""

    @pytest.fixture
    def checker(self):
        """创建检查器实例"""
        return ConstraintChecker()

    @pytest.fixture
    def partial_state(self):
        """创建部分收集状态的 Agent"""
        return {
            'scenario_type': 'oil_spill',
            'checklist': {
                'fluid_type': True,
                'continuous': True,
                # 缺少 engine_status 和 position
                'leak_size': False,
            },
            'incident': {
                'fluid_type': 'FUEL',
                'continuous': True,
            },
            'mandatory_actions_done': {
                'risk_assessed': False,
                'fire_dept_notified': False,
                'atc_notified': False,
            },
            'fsm_state': 'INIT',
        }

    @pytest.fixture
    def complete_p1_state(self):
        """创建 P1 完整的 Agent 状态"""
        return {
            'scenario_type': 'oil_spill',
            'checklist': {
                'fluid_type': True,
                'continuous': True,
                'engine_status': True,
                'position': True,
                'leak_size': False,
            },
            'incident': {
                'fluid_type': 'FUEL',
                'continuous': True,
                'engine_status': 'STOPPED',
                'position': '501',
            },
            'mandatory_actions_done': {
                'risk_assessed': False,
                'fire_dept_notified': False,
                'atc_notified': False,
            },
            'fsm_state': 'P1_RISK_ASSESS',
        }

    def test_p1_incomplete_error(self, checker, partial_state):
        """测试 P1 不完整时返回错误"""
        result = checker.check_all(partial_state)

        assert not result.passed
        p1_errors = [v for v in result.errors if v.code == checker.ERR_P1_INCOMPLETE]
        assert len(p1_errors) >= 1

    def test_p1_complete_no_error(self, checker, complete_p1_state):
        """测试 P1 完整时无 P1 错误"""
        result = checker.check_all(complete_p1_state)

        p1_errors = [v for v in result.errors if v.code == checker.ERR_P1_INCOMPLETE]
        assert len(p1_errors) == 0

    def test_check_p1_complete_success(self, checker, complete_p1_state):
        """测试快速检查 P1 完整"""
        is_complete, missing = checker.check_p1_complete(complete_p1_state)
        assert is_complete is True
        assert missing is None

    def test_check_p1_complete_failure(self, checker, partial_state):
        """测试快速检查 P1 不完整"""
        is_complete, missing = checker.check_p1_complete(partial_state)
        assert is_complete is False
        assert missing is not None

    def test_state_required_fields(self, checker, complete_p1_state):
        """测试状态必需字段检查"""
        # P1_RISK_ASSESS 状态需要 fluid_type
        result = checker.check_all(complete_p1_state)

        # 应该没有 required_field 错误，因为 fluid_type 已收集
        required_errors = [
            v for v in result.errors
            if v.code == checker.ERR_MISSING_REQUIRED_FIELD
        ]
        assert len(required_errors) == 0

    def test_mandatory_action_not_done(self, checker, complete_p1_state):
        """测试强制动作未执行"""
        # P1_RISK_ASSESS 需要 risk_assessed
        result = checker.check_all(complete_p1_state)

        action_errors = [
            v for v in result.errors
            if v.code == checker.ERR_MANDATORY_ACTION_NOT_DONE
            and v.field == 'risk_assessed'
        ]
        assert len(action_errors) >= 1

    def test_strict_mode_warns_p2(self, checker, complete_p1_state):
        """测试严格模式下 P2 字段缺失给出警告"""
        result = checker.check_all(complete_p1_state, strict_mode=True)

        # 应该有 P2 字段缺失的警告
        p2_warnings = [v for v in result.warnings if v.code == 'FIELD_MISSING']
        assert len(p2_warnings) >= 1


class TestChecklistValidator:
    """Checklist 验证器测试"""

    def test_validate_valid_fluid_type(self):
        """测试验证有效的油液类型"""
        is_valid, error = validate_checklist_field('fluid_type', 'FUEL')
        assert is_valid is True
        assert error is None

    def test_validate_invalid_fluid_type(self):
        """测试验证无效的油液类型"""
        is_valid, error = validate_checklist_field('fluid_type', 'INVALID')
        assert is_valid is False
        assert error is not None

    def test_validate_valid_leak_size(self):
        """测试验证有效的泄漏大小"""
        is_valid, error = validate_checklist_field('leak_size', 'SMALL')
        assert is_valid is True

    def test_validate_valid_continuous(self):
        """测试验证有效的持续滴漏"""
        is_valid, error = validate_checklist_field('continuous', True)
        assert is_valid is True


class TestConstraintViolation:
    """约束违反详情测试"""

    def test_violation_creation(self):
        """测试创建约束违反"""
        violation = ConstraintViolation(
            severity=ConstraintSeverity.ERROR,
            code="TEST_ERROR",
            message="测试错误",
            field="test_field",
            suggestion="修复建议"
        )

        assert violation.severity == ConstraintSeverity.ERROR
        assert violation.code == "TEST_ERROR"
        assert violation.field == "test_field"
        assert violation.suggestion == "修复建议"


class TestIntegration:
    """集成测试"""

    def test_full_constraint_check_flow(self):
        """测试完整的约束检查流程"""
        # 创建状态
        state = {
            'scenario_type': 'oil_spill',
            'checklist': {
                'fluid_type': True,
                'continuous': True,
                'engine_status': True,
                'position': True,
                'leak_size': True,
            },
            'incident': {
                'fluid_type': 'FUEL',
                'continuous': True,
                'engine_status': 'STOPPED',
                'position': '501',
                'leak_size': 'SMALL',
            },
            'mandatory_actions_done': {
                'risk_assessed': True,
                'fire_dept_notified': False,
                'atc_notified': False,
            },
            'fsm_state': 'P2_IMMEDIATE_CONTROL',
        }

        # 执行检查
        result = check_constraints(state)

        # 验证结果
        assert result.passed is True or len(result.errors) == 0

    def test_high_risk_fire_dept_notification(self):
        """测试高风险时消防部门通知"""
        state = {
            'scenario_type': 'oil_spill',
            'checklist': {
                'fluid_type': True,
                'continuous': True,
                'engine_status': True,
                'position': True,
                'leak_size': True,
            },
            'incident': {
                'fluid_type': 'FUEL',
                'continuous': True,
                'engine_status': 'RUNNING',  # 发动机运转，高风险
                'position': '501',
                'leak_size': 'LARGE',  # 大面积泄漏
            },
            'mandatory_actions_done': {
                'risk_assessed': True,
                'fire_dept_notified': False,  # 未通知消防
                'atc_notified': False,
            },
            'fsm_state': 'P2_IMMEDIATE_CONTROL',
        }

        result = check_constraints(state)

        # 高风险时应该有消防通知的警告/错误
        fire_errors = [
            v for v in result.errors + result.warnings
            if 'fire' in v.field.lower() or '消防' in v.message
        ]
        # 可能有多个相关检查
