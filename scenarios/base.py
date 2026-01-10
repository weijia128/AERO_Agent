"""
场景基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, TypedDict
from pathlib import Path
import yaml


class ScenarioConfig(TypedDict):
    """场景配置类型"""
    metadata: Dict[str, Any]
    settings: Dict[str, Any]
    checklist: Dict[str, Any]
    fsm_states: List[Dict[str, Any]]
    mandatory_triggers: List[Dict[str, Any]]
    risk_rules: List[Dict[str, Any]]
    spatial_config: Dict[str, Any]
    notifications: Dict[str, Any]
    report_template: Dict[str, Any]
    prompt_config: Dict[str, Any]


class BaseScenario(ABC):
    """场景基类"""

    name: str = ""
    version: str = "1.0"
    config_path: Optional[Path] = None
    checklist_path: Optional[Path] = None
    fsm_states_path: Optional[Path] = None
    prompt_path: Optional[Path] = None

    def __init__(self):
        self._config: Optional[ScenarioConfig] = None
        self._checklist: Optional[Dict[str, Any]] = None
        self._fsm_states: Optional[List[Dict[str, Any]]] = None
        self._prompt_config: Optional[Dict[str, Any]] = None

    def _load_yaml(self, path: Optional[Path]) -> Dict[str, Any]:
        """加载 YAML 配置文件"""
        if path and path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}

    def _load_config(self) -> ScenarioConfig:
        """加载完整场景配置"""
        if self._config is not None:
            return self._config

        base_dir = self.config_path.parent if self.config_path else Path(__file__).parent

        # 加载主配置
        main_config = self._load_yaml(self.config_path) if self.config_path else {}

        # 加载子配置
        checklist = self._load_yaml(
            base_dir / "checklist.yaml" if not self.checklist_path else self.checklist_path
        )
        fsm_states = self._load_yaml(
            base_dir / "fsm_states.yaml" if not self.fsm_states_path else self.fsm_states_path
        )
        prompt_config = self._load_yaml(
            base_dir / "prompt.yaml" if not self.prompt_path else self.prompt_path
        )

        # 合并配置
        self._config = {
            "metadata": main_config.get("scenario", {}),
            "settings": main_config.get("settings", {}),
            "checklist": checklist.get("checklist", {}),
            "fsm_states": fsm_states.get("fsm_states", []),
            "mandatory_triggers": main_config.get("mandatory_triggers", []),
            "risk_rules": main_config.get("risk_rules", []),
            "spatial_config": main_config.get("spatial_config", {}),
            "notifications": main_config.get("notifications", {}),
            "report_template": main_config.get("report_template", {}),
            "prompt_config": prompt_config,
        }

        return self._config

    @property
    def config(self) -> ScenarioConfig:
        """获取完整配置"""
        return self._load_config()

    @property
    def metadata(self) -> Dict[str, Any]:
        """获取元信息"""
        return self._load_config().get("metadata", {})

    @property
    def settings(self) -> Dict[str, Any]:
        """获取设置"""
        return self._load_config().get("settings", {})

    @property
    def checklist(self) -> Dict[str, Any]:
        """获取 Checklist 配置"""
        if self._checklist is None:
            self._checklist = self._load_config().get("checklist", {})
        return self._checklist

    @property
    def p1_fields(self) -> List[Dict[str, Any]]:
        """获取 P1 字段列表"""
        return self.checklist.get("p1_fields", [])

    @property
    def p2_fields(self) -> List[Dict[str, Any]]:
        """获取 P2 字段列表"""
        return self.checklist.get("p2_fields", [])

    @property
    def fsm_states(self) -> List[Dict[str, Any]]:
        """获取 FSM 状态配置"""
        if self._fsm_states is None:
            self._fsm_states = self._load_config().get("fsm_states", [])
        return self._fsm_states

    @property
    def fsm_transitions(self) -> List[Dict[str, Any]]:
        """获取 FSM 转换配置"""
        fsm_data = self._load_yaml(
            self.fsm_states_path if self.fsm_states_path
            else (self.config_path.parent / "fsm_states.yaml" if self.config_path else None)
        )
        return fsm_data.get("transitions", [])

    @property
    def mandatory_triggers(self) -> List[Dict[str, Any]]:
        """获取强制触发规则"""
        return self._load_config().get("mandatory_triggers", [])

    @property
    def risk_rules(self) -> List[Dict[str, Any]]:
        """获取风险评估规则"""
        return self._load_config().get("risk_rules", [])

    @property
    def spatial_config(self) -> Dict[str, Any]:
        """获取空间配置"""
        return self._load_config().get("spatial_config", {})

    @property
    def notifications(self) -> Dict[str, Any]:
        """获取通知配置"""
        return self._load_config().get("notifications", {})

    @property
    def report_template(self) -> Dict[str, Any]:
        """获取报告模板"""
        return self._load_config().get("report_template", {})

    @property
    def prompt_config(self) -> Dict[str, Any]:
        """获取 Prompt 配置"""
        if self._prompt_config is None:
            self._prompt_config = self._load_config().get("prompt_config", {})
        return self._prompt_config

    @property
    def system_prompt(self) -> str:
        """获取场景 System Prompt"""
        return self.prompt_config.get("system_prompt", "")

    @property
    def field_order(self) -> List[str]:
        """获取字段收集顺序"""
        return self.prompt_config.get("field_order", [])

    @property
    def field_names(self) -> Dict[str, str]:
        """获取字段中文名称映射"""
        return self.prompt_config.get("field_names", {})

    def get_ask_prompt_by_key(self, field_key: str) -> str:
        """根据字段 key 获取追问提示"""
        return self.prompt_config.get("ask_prompts", {}).get(field_key, f"请提供{field_key}信息？")

    def get_field_name(self, field_key: str) -> str:
        """获取字段的中文名称"""
        return self.field_names.get(field_key, field_key)

    def sort_checklist_by_priority(self, checklist: Dict[str, bool]) -> List[str]:
        """按场景定义的顺序返回未收集的字段列表"""
        field_order = self.field_order
        missing_fields = [f for f, v in checklist.items() if not v]

        # 按 field_order 排序
        sorted_missing = []
        for field in field_order:
            if field in missing_fields:
                sorted_missing.append(field)
        # 添加不在 field_order 中的字段
        for field in missing_fields:
            if field not in sorted_missing:
                sorted_missing.append(field)

        return sorted_missing

    def get_checklist_field(self, field_key: str) -> Optional[Dict[str, Any]]:
        """根据 key 获取 checklist 字段配置"""
        for field in self.p1_fields:
            if field.get("key") == field_key:
                return field
        for field in self.p2_fields:
            if field.get("key") == field_key:
                return field
        return None

    def get_ask_prompt(self, field_key: str) -> Optional[str]:
        """获取字段的追问提示"""
        field = self.get_checklist_field(field_key)
        return field.get("ask_prompt") if field else None

    @abstractmethod
    def get_tools(self) -> List[str]:
        """获取场景相关工具列表"""
        pass


class OilSpillScenario(BaseScenario):
    """漏油场景"""

    name = "oil_spill"
    version = "1.0"
    config_path = Path(__file__).parent / "oil_spill" / "config.yaml"
    checklist_path = Path(__file__).parent / "oil_spill" / "checklist.yaml"
    fsm_states_path = Path(__file__).parent / "oil_spill" / "fsm_states.yaml"
    prompt_path = Path(__file__).parent / "oil_spill" / "prompt.yaml"

    def get_tools(self) -> List[str]:
        return [
            "ask_for_detail",
            "get_aircraft_info",
            "get_stand_location",
            "calculate_impact_zone",
            "search_regulations",
            "assess_risk",
            "notify_department",
            "generate_report",
        ]


class ScenarioRegistry:
    """场景注册中心"""

    _scenarios: Dict[str, BaseScenario] = {}

    @classmethod
    def register(cls, scenario: BaseScenario):
        """注册场景"""
        cls._scenarios[scenario.name] = scenario

    @classmethod
    def get(cls, name: str) -> Optional[BaseScenario]:
        """获取场景"""
        return cls._scenarios.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        """列出所有场景"""
        return list(cls._scenarios.keys())

    @classmethod
    def get_checklist_field(cls, scenario_name: str, field_key: str) -> Optional[Dict[str, Any]]:
        """获取场景的 checklist 字段配置"""
        scenario = cls.get(scenario_name)
        if scenario:
            return scenario.get_checklist_field(field_key)
        return None


# 注册默认场景
ScenarioRegistry.register(OilSpillScenario())
