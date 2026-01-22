"""
场景基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, TypedDict, cast
from pathlib import Path
import yaml  # type: ignore[import-untyped]

from scenarios.schema import ScenarioManifest


class ScenarioConfig(TypedDict):
    """场景配置类型"""
    metadata: Dict[str, Any]
    settings: Dict[str, Any]
    checklist: Dict[str, Any]
    fsm_states: List[Dict[str, Any]]
    mandatory_triggers: List[Dict[str, Any]]
    risk_rules: List[Dict[str, Any]]
    immediate_actions: Dict[str, List[str]]
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
            "immediate_actions": main_config.get("immediate_actions", {}),
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
    def keywords(self) -> List[str]:
        """场景识别关键词（用于自动分类）"""
        meta = self.metadata or {}
        return cast(List[str], meta.get("keywords", []))

    @property
    def summary_prompts(self) -> Dict[str, Any]:
        """报告摘要 prompt 配置"""
        return cast(
            Dict[str, Any],
            getattr(self, "_summary_prompts", None) or self.config.get("summary_prompts", {}),
        )

    @property
    def regex_patterns(self) -> Dict[str, List[Dict[str, str]]]:
        """场景专属的正则/枚举提取规则"""
        return cast(
            Dict[str, List[Dict[str, str]]],
            getattr(self, "_regex", None) or self.config.get("regex", {}),
        )

    @property
    def template_path(self) -> Optional[str]:
        """场景自定义模板路径（相对模板根目录）"""
        return getattr(self, "_template_path", None)

    @property
    def settings(self) -> Dict[str, Any]:
        """获取设置"""
        return self._load_config().get("settings", {})

    @property
    def risk_required(self) -> bool:
        """是否必须完成风险评估"""
        return bool(self.settings.get("risk_required", True))

    @property
    def checklist(self) -> Dict[str, Any]:
        """获取 Checklist 配置"""
        if self._checklist is None:
            self._checklist = self._load_config().get("checklist", {})
        return self._checklist

    @property
    def p1_fields(self) -> List[Dict[str, Any]]:
        """获取 P1 字段列表"""
        return cast(List[Dict[str, Any]], self.checklist.get("p1_fields", []))

    @property
    def p2_fields(self) -> List[Dict[str, Any]]:
        """获取 P2 字段列表"""
        return cast(List[Dict[str, Any]], self.checklist.get("p2_fields", []))

    @property
    def fsm_states(self) -> List[Dict[str, Any]]:
        """获取 FSM 状态配置"""
        if self._fsm_states is None:
            self._fsm_states = cast(
                List[Dict[str, Any]],
                self._load_config().get("fsm_states", []),
            )
        return self._fsm_states

    @property
    def fsm_transitions(self) -> List[Dict[str, Any]]:
        """获取 FSM 转换配置"""
        fsm_data = self._load_yaml(
            self.fsm_states_path if self.fsm_states_path
            else (self.config_path.parent / "fsm_states.yaml" if self.config_path else None)
        )
        return cast(List[Dict[str, Any]], fsm_data.get("transitions", []))

    @property
    def mandatory_triggers(self) -> List[Dict[str, Any]]:
        """获取强制触发规则"""
        return cast(List[Dict[str, Any]], self._load_config().get("mandatory_triggers", []))

    @property
    def risk_rules(self) -> List[Dict[str, Any]]:
        """获取风险评估规则"""
        return cast(List[Dict[str, Any]], self._load_config().get("risk_rules", []))

    @property
    def immediate_actions(self) -> Dict[str, List[str]]:
        """获取场景专属立即行动配置"""
        return self._load_config().get("immediate_actions", {})

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
        return str(self.prompt_config.get("system_prompt", ""))

    @property
    def field_order(self) -> List[str]:
        """获取字段收集顺序"""
        return cast(List[str], self.prompt_config.get("field_order", []))

    @property
    def field_names(self) -> Dict[str, str]:
        """获取字段中文名称映射"""
        return cast(Dict[str, str], self.prompt_config.get("field_names", {}))

    def get_ask_prompt_by_key(self, field_key: str) -> str:
        """根据字段 key 获取追问提示"""
        prompts = cast(Dict[str, str], self.prompt_config.get("ask_prompts", {}))
        return prompts.get(field_key, f"请提供{field_key}信息？")

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


class BirdStrikeScenario(BaseScenario):
    """鸟击场景"""

    name = "bird_strike"
    version = "1.0"
    config_path = Path(__file__).parent / "bird_strike" / "config.yaml"
    checklist_path = Path(__file__).parent / "bird_strike" / "checklist.yaml"
    fsm_states_path = Path(__file__).parent / "bird_strike" / "fsm_states.yaml"
    prompt_path = Path(__file__).parent / "bird_strike" / "prompt.yaml"

    def get_tools(self) -> List[str]:
        return [
            "ask_for_detail",
            "get_aircraft_info",
            "assess_bird_strike_risk",
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

    @classmethod
    def auto_register_from_manifests(cls, base_dir: Optional[Path] = None):
        """扫描目录下的 manifest.yaml 自动注册场景，减少代码改动"""
        root = base_dir or Path(__file__).parent
        for manifest_path in root.glob("*/manifest.yaml"):
            scenario = ManifestScenario(manifest_path)
            if scenario.name:
                cls.register(scenario)


class ManifestScenario(BaseScenario):
    """基于 manifest.yaml 的场景定义，便于无代码扩展"""

    def __init__(self, manifest_path: Path):
        super().__init__()
        self.manifest_path = manifest_path
        manifest_data = self._load_yaml(manifest_path) or {}
        manifest = ScenarioManifest.from_yaml(manifest_path, manifest_data)

        # 允许在实例级覆盖 class 属性
        self.name = manifest.name or self.name
        self.version = manifest_data.get("scenario", {}).get("version", "1.0")
        self.config_path = manifest.config_path
        self.checklist_path = manifest.checklist_path
        self.fsm_states_path = manifest.fsm_states_path
        self.prompt_path = manifest.prompt_path
        self._template_path = manifest.template_path
        self._tools = manifest.tools
        self._regex = manifest.regex
        self._summary_prompts = manifest.summary_prompts

    def get_tools(self) -> List[str]:
        return self._tools or []


# 注册默认场景
ScenarioRegistry.register(OilSpillScenario())
ScenarioRegistry.register(BirdStrikeScenario())
# 自动注册 manifest 中的场景（新增场景时仅需放置 manifest + 配套文件）
ScenarioRegistry.auto_register_from_manifests()
