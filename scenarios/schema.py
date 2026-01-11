from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ScenarioManifest:
    name: str
    priority: int = 100
    keywords: List[str] = field(default_factory=list)
    config_path: Optional[Path] = None
    checklist_path: Optional[Path] = None
    fsm_states_path: Optional[Path] = None
    prompt_path: Optional[Path] = None
    template_path: Optional[str] = None
    tools: List[str] = field(default_factory=list)
    regex: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    summary_prompts: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, manifest_path: Path, data: Dict[str, Any]) -> "ScenarioManifest":
        scenario = data.get("scenario", {})
        paths = data.get("paths", {})
        prompt_config = data.get("prompts", {})

        def _path(key: str, default: str) -> Optional[Path]:
            val = paths.get(key) if paths else None
            return manifest_path.parent / val if val else manifest_path.parent / default

        return cls(
            name=scenario.get("name", ""),
            priority=scenario.get("priority", 100),
            keywords=scenario.get("keywords", []),
            config_path=_path("config", "config.yaml"),
            checklist_path=_path("checklist", "checklist.yaml"),
            fsm_states_path=_path("fsm_states", "fsm_states.yaml"),
            prompt_path=_path("prompt", "prompt.yaml"),
            template_path=paths.get("template") if paths else None,
            tools=data.get("tools", []),
            regex=data.get("regex", {}),
            summary_prompts=prompt_config.get("summary", {}),
        )
