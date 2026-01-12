from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from config.settings import settings


def _format_risk_level(level: str) -> str:
    """格式化风险等级为中文标签。"""
    mapping = {
        "R4": "严重",
        "R3": "高",
        "R2": "中",
        "R1": "低",
        "HIGH": "高",
        "MEDIUM_HIGH": "中高",
        "MEDIUM": "中",
        "LOW": "低",
    }
    return mapping.get(level, level or "未评估")


def _format_datetime(iso_string: str) -> str:
    """格式化 ISO 时间字符串为可读时间。"""
    if not iso_string:
        return "——"
    return iso_string[:19].replace("T", " ")


env = Environment(
    loader=FileSystemLoader(settings.TEMPLATE_ROOT),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    auto_reload=settings.JINJA_AUTO_RELOAD,
    cache_size=settings.JINJA_CACHE_SIZE,
)
env.filters["risk_level"] = _format_risk_level
env.filters["datetime"] = _format_datetime


def render_report(
    scenario_type: str,
    context: Dict[str, Any],
    template_path: Optional[str] = None,
) -> str:
    """按场景渲染报告，未找到场景模板则回退基础模板。"""
    template_path = template_path or f"{scenario_type}/report.md.j2"
    try:
        template = env.get_template(template_path)
    except TemplateNotFound:
        template = env.get_template("base_report.md.j2")
    return template.render(**context)
