"""
清理时间预估工具

基于规则和气象条件预估清理时间
"""
from typing import Dict, Any, Optional
from tools.base import BaseTool


# 基准清理时间（分钟）
BASE_CLEANUP_TIME = {
    "FUEL": {
        "SMALL": {"stand": 20, "taxiway": 25, "runway": 30},
        "MEDIUM": {"stand": 30, "taxiway": 40, "runway": 50},
        "LARGE": {"stand": 45, "taxiway": 60, "runway": 90},
    },
    "HYDRAULIC": {
        "SMALL": {"stand": 15, "taxiway": 20, "runway": 25},
        "MEDIUM": {"stand": 25, "taxiway": 35, "runway": 45},
        "LARGE": {"stand": 35, "taxiway": 50, "runway": 70},
    },
    "OIL": {
        "SMALL": {"stand": 10, "taxiway": 15, "runway": 20},
        "MEDIUM": {"stand": 20, "taxiway": 30, "runway": 40},
        "LARGE": {"stand": 30, "taxiway": 45, "runway": 60},
    },
}


class EstimateCleanupTimeTool(BaseTool):
    """预估清理时间工具"""

    name = "estimate_cleanup_time"
    description = """基于规则和气象条件预估清理时间。

输入参数:
- fluid_type: 油液类型 (FUEL/HYDRAULIC/OIL)
- leak_size: 泄漏面积 (SMALL/MEDIUM/LARGE)
- position_type: 位置类型 (stand/taxiway/runway)

返回信息:
- 基准清理时间
- 气象调整后时间
- 调整因子详情"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 获取参数
        fluid_type = inputs.get("fluid_type") or state.get("incident", {}).get("fluid_type", "FUEL")
        leak_size = inputs.get("leak_size") or state.get("incident", {}).get("leak_size", "MEDIUM")
        position = inputs.get("position") or state.get("incident", {}).get("position", "")

        # 2. 确定位置类型
        position_type = self._determine_position_type(position, state)

        # 3. 获取基准时间
        base_time = self._get_base_time(fluid_type, leak_size, position_type)

        # 4. 获取气象调整系数
        weather_impact = state.get("weather_impact", {})
        weather_factor = weather_impact.get("cleanup_time_adjustment", {}).get("total_factor", 1.0)

        # 5. 计算调整后时间
        adjusted_time = int(base_time * weather_factor)

        # 6. 构建返回结果
        observation = self._format_observation(
            base_time, adjusted_time, weather_factor,
            fluid_type, leak_size, position_type
        )

        return {
            "observation": observation,
            "cleanup_time_estimate": {
                "base_time_minutes": base_time,
                "weather_factor": weather_factor,
                "adjusted_time_minutes": adjusted_time,
                "fluid_type": fluid_type,
                "leak_size": leak_size,
                "position_type": position_type
            }
        }

    def _determine_position_type(self, position: str, state: Dict[str, Any]) -> str:
        """确定位置类型"""
        if not position:
            return "stand"  # 默认机位

        pos_lower = position.lower()

        # 判断跑道
        if "runway" in pos_lower or (pos_lower.endswith(("l", "r", "c")) and len(pos_lower) <= 3):
            return "runway"

        # 判断滑行道
        if "taxiway" in pos_lower or pos_lower.startswith(("a", "b", "c", "d", "e", "f")):
            return "taxiway"

        # 默认机位
        return "stand"

    def _get_base_time(self, fluid_type: str, leak_size: str, position_type: str) -> int:
        """获取基准清理时间"""
        fluid_rules = BASE_CLEANUP_TIME.get(fluid_type, BASE_CLEANUP_TIME["FUEL"])
        size_rules = fluid_rules.get(leak_size, fluid_rules["MEDIUM"])
        return size_rules.get(position_type, size_rules["stand"])

    def _format_observation(
        self,
        base_time: int,
        adjusted_time: int,
        weather_factor: float,
        fluid_type: str,
        leak_size: str,
        position_type: str
    ) -> str:
        """格式化输出"""
        lines = ["清理时间预估完成:"]

        # 基准时间
        lines.append(f"📋 基准清理时间: {base_time}分钟")
        lines.append(f"   (油液类型: {fluid_type}, 泄漏面积: {leak_size}, 位置: {position_type})")

        # 气象调整
        if weather_factor != 1.0:
            lines.append(f"🌦️  气象调整系数: {weather_factor:.2f}")
            lines.append(f"⏱️  调整后预估时间: {adjusted_time}分钟")

            if weather_factor > 1.0:
                diff = adjusted_time - base_time
                lines.append(f"   （气象条件不利，增加 {diff} 分钟）")
            else:
                diff = base_time - adjusted_time
                lines.append(f"   （气象条件有利，减少 {diff} 分钟）")
        else:
            lines.append(f"⏱️  预估清理时间: {adjusted_time}分钟 (气象条件标准)")

        return "\n".join(lines)
