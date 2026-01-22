"""
约束加载器

从场景配置 YAML 文件加载约束定义，包括：
1. Checklist 字段约束（必填字段、优先级）
2. 强制动作约束（必须执行的动作）
3. 状态转换约束（状态间的依赖关系）
"""
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field as dataclass_field
import yaml  # type: ignore[import-untyped]


@dataclass
class ChecklistField:
    """Checklist 字段定义"""
    field: str
    key: str
    label: str
    field_type: str
    required: bool
    priority: str  # P1 or P2
    options: List[Dict[str, str]] = dataclass_field(default_factory=list)
    ask_prompt: str = ""
    validation: str = ""


@dataclass
class MandatoryAction:
    """强制动作定义"""
    action: str
    condition: str  # 触发条件
    description: str = ""
    params: Dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass
class StateConstraint:
    """状态约束定义"""
    state_id: str
    required_checklist_fields: List[str] = dataclass_field(default_factory=list)
    required_mandatory_actions: List[Union[str, Dict[str, Any]]] = dataclass_field(
        default_factory=list
    )
    triggers: List[Dict[str, Any]] = dataclass_field(default_factory=list)


@dataclass
class ScenarioConstraints:
    """场景约束集合"""
    scenario_type: str
    p1_fields: List[ChecklistField] = dataclass_field(default_factory=list)
    p2_fields: List[ChecklistField] = dataclass_field(default_factory=list)
    mandatory_actions: List[MandatoryAction] = dataclass_field(default_factory=list)
    state_constraints: Dict[str, StateConstraint] = dataclass_field(default_factory=dict)


class ConstraintLoader:
    """约束加载器"""

    def __init__(self, base_path: Optional[str] = None):
        """
        初始化约束加载器

        Args:
            base_path: 场景配置的基础路径，默认从项目根目录加载
        """
        if base_path is None:
            # 默认从项目根目录的 scenarios 目录加载
            self.base_path = Path(__file__).parent.parent / "scenarios"
        else:
            self.base_path = Path(base_path)

        self._cache: Dict[str, ScenarioConstraints] = {}

    def load(self, scenario_type: str) -> ScenarioConstraints:
        """
        加载指定场景的约束配置

        Args:
            scenario_type: 场景类型 (如 'oil_spill')

        Returns:
            ScenarioConstraints 对象

        Raises:
            FileNotFoundError: 场景配置文件不存在
            ValueError: 场景类型无效
        """
        # 检查缓存
        if scenario_type in self._cache:
            return self._cache[scenario_type]

        scenario_path = self.base_path / scenario_type
        if not scenario_path.exists():
            raise FileNotFoundError(f"场景配置不存在: {scenario_path}")

        # 加载 config.yaml
        config_file = scenario_path / "config.yaml"
        config: Dict[str, Any] = {}
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

        # 加载 checklist.yaml
        checklist_file = scenario_path / "checklist.yaml"
        if not checklist_file.exists():
            raise FileNotFoundError(f"Checklist 配置文件不存在: {checklist_file}")

        with open(checklist_file, 'r', encoding='utf-8') as f:
            checklist_config: Dict[str, Any] = yaml.safe_load(f) or {}

        # 加载 fsm_states.yaml
        fsm_file = scenario_path / "fsm_states.yaml"
        fsm_config: Dict[str, Any] = {}
        if fsm_file.exists():
            with open(fsm_file, 'r', encoding='utf-8') as f:
                fsm_config = yaml.safe_load(f) or {}

        # 构建约束对象
        constraints = self._build_constraints(scenario_type, checklist_config, fsm_config, config)

        # 缓存
        self._cache[scenario_type] = constraints

        return constraints

    def _build_constraints(
        self,
        scenario_type: str,
        checklist_config: Dict[str, Any],
        fsm_config: Dict[str, Any],
        config: Dict[str, Any],
    ) -> ScenarioConstraints:
        """构建约束对象"""
        constraints = ScenarioConstraints(scenario_type=scenario_type)

        # 解析 checklist 配置
        checklist = checklist_config.get('checklist', {})
        done_condition = checklist.get('done_condition', {})

        # P1 字段
        for field_def in checklist.get('p1_fields', []):
            constraints.p1_fields.append(self._parse_checklist_field(field_def))

        # P2 字段
        for field_def in checklist.get('p2_fields', []):
            constraints.p2_fields.append(self._parse_checklist_field(field_def))

        # 解析 FSM 状态约束
        for state_def in fsm_config.get('fsm_states', []):
            state_id = state_def.get('id')
            if state_id:
                # 处理 required_mandatory_actions (支持字符串和字典两种格式)
                required_mas: List[Union[str, Dict[str, Any]]] = []
                for ma in state_def.get('required_mandatory_actions', []):
                    if isinstance(ma, str):
                        required_mas.append(ma)
                    elif isinstance(ma, dict) and 'action' in ma:
                        required_mas.append(ma['action'])

                state_constraint = StateConstraint(
                    state_id=state_id,
                    required_checklist_fields=state_def.get('required_checklist_fields', []),
                    required_mandatory_actions=required_mas,
                    triggers=state_def.get('triggers', [])
                )
                constraints.state_constraints[state_id] = state_constraint

        # 解析强制动作（统一来源：config.yaml 的 mandatory_triggers）
        for trigger in config.get("mandatory_triggers", []) or []:
            action = trigger.get("action", "")
            condition = trigger.get("condition", {})
            if action and condition:
                constraints.mandatory_actions.append(MandatoryAction(
                    action=action,
                    condition=condition,
                    description=trigger.get("description", ""),
                    params=trigger.get("params", {})
                ))

        return constraints

    def _parse_checklist_field(self, field_def: Dict) -> ChecklistField:
        """解析 Checklist 字段定义"""
        options = []
        for opt in field_def.get('options', []):
            options.append({
                'value': opt.get('value', ''),
                'label': opt.get('label', '')
            })

        # 处理 validation 字段（可能是字典或字符串）
        validation = field_def.get('validation', '')
        if isinstance(validation, dict):
            validation = validation.get('regex', '')

        return ChecklistField(
            field=field_def.get('field', ''),
            key=field_def.get('key', ''),
            label=field_def.get('label', ''),
            field_type=field_def.get('type', 'string'),
            required=field_def.get('required', False),
            priority=field_def.get('priority', 'P2'),
            options=options,
            ask_prompt=field_def.get('ask_prompt', ''),
            validation=validation
        )

    def get_required_fields_for_state(self, scenario_type: str, state: str) -> List[str]:
        """获取指定状态必需的 checklist 字段"""
        constraints = self.load(scenario_type)
        state_constraint = constraints.state_constraints.get(state)
        if state_constraint:
            return state_constraint.required_checklist_fields
        return []

    def get_all_p1_keys(self, scenario_type: str) -> List[str]:
        """获取所有 P1 字段的 key"""
        constraints = self.load(scenario_type)
        return [f.key for f in constraints.p1_fields]

    def get_all_p2_keys(self, scenario_type: str) -> List[str]:
        """获取所有 P2 字段的 key"""
        constraints = self.load(scenario_type)
        return [f.key for f in constraints.p2_fields]

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局加载器实例
_default_loader: Optional[ConstraintLoader] = None


def get_loader() -> ConstraintLoader:
    """获取全局约束加载器实例"""
    global _default_loader
    if _default_loader is None:
        _default_loader = ConstraintLoader()
    return _default_loader


def load_constraints(scenario_type: str) -> ScenarioConstraints:
    """便捷函数：加载场景约束"""
    return get_loader().load(scenario_type)
