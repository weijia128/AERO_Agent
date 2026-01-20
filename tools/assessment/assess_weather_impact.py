"""
气象影响评估工具

分析气象条件对油污扩散和清理的影响
"""
from typing import Dict, Any, Optional
from tools.base import BaseTool
from tools.information.get_weather import get_weather_data
import math


class AssessWeatherImpactTool(BaseTool):
    """评估气象条件对事故处置的影响"""

    name = "assess_weather_impact"
    description = """分析气象条件对油污扩散和清理的影响。

输入参数:
- fluid_type: 油液类型 (FUEL/HYDRAULIC/OIL)
- leak_size: 泄漏面积 (SMALL/MEDIUM/LARGE, 可选)
- position: 事发位置（用于查询气象）

返回信息:
- 风向对扩散方向的影响
- 风速对扩散速率的影响
- 温度对油液特性的影响
- 能见度对清理作业的影响
- 调整后的清理时间预估"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 获取参数
        fluid_type = inputs.get("fluid_type") or state.get("incident", {}).get("fluid_type", "FUEL")
        leak_size = inputs.get("leak_size") or state.get("incident", {}).get("leak_size")
        position = inputs.get("position") or state.get("incident", {}).get("position")

        # 2. 获取气象数据（从状态或重新查询）
        weather = state.get("weather", {})
        if not weather and position:
            # 如果状态中没有气象数据，查询一次
            from tools.information.get_weather import GetWeatherTool
            weather_tool = GetWeatherTool()
            result = weather_tool.execute(state, {"location": position})
            weather = result.get("weather", {})

        if not weather:
            return {"observation": "缺少气象数据，无法评估气象影响"}

        # 3. 分析风向风速影响
        wind_impact = self._analyze_wind_impact(weather)

        # 4. 分析温度影响
        temperature_impact = self._analyze_temperature_impact(weather, fluid_type)

        # 5. 分析能见度影响
        visibility_impact = self._analyze_visibility_impact(weather)

        # 6. 计算清理时间调整系数
        cleanup_adjustment = self._calculate_cleanup_adjustment(
            wind_impact, temperature_impact, visibility_impact, fluid_type
        )

        # 7. 构建返回结果
        weather_impact = {
            "wind_impact": wind_impact,
            "temperature_impact": temperature_impact,
            "visibility_impact": visibility_impact,
            "cleanup_time_adjustment": cleanup_adjustment
        }

        observation = self._format_observation(weather_impact, weather)

        return {
            "observation": observation,
            "weather_impact": weather_impact
        }

    def _analyze_wind_impact(self, weather: Dict[str, Any]) -> Dict[str, Any]:
        """分析风向风速影响"""
        wind_direction = weather.get("wind_direction")  # 度数 0-360
        wind_speed = weather.get("wind_speed") or 0  # m/s, 处理None值

        # 风速分级
        if wind_speed < 2:
            spread_rate = "缓慢"
            radius_adjustment = 0
        elif wind_speed < 5:
            spread_rate = "中等"
            radius_adjustment = 0
        else:
            spread_rate = "快速"
            radius_adjustment = 1  # BFS跳数+1

        # 风向描述 (注意: 0度是有效值,不能用 if wind_direction)
        spread_direction = self._wind_direction_to_text(wind_direction) if wind_direction is not None else "未知"

        return {
            "wind_direction_degrees": wind_direction,
            "wind_speed_ms": wind_speed,
            "spread_direction": spread_direction,
            "spread_rate": spread_rate,
            "radius_adjustment": radius_adjustment
        }

    def _analyze_temperature_impact(self, weather: Dict[str, Any], fluid_type: str) -> Dict[str, Any]:
        """分析温度影响"""
        temperature = weather.get("temperature")

        if temperature is None:
            return {
                "volatility": "未知",
                "viscosity": "未知",
                "cleanup_difficulty": "未知",
                "time_factor": 1.0
            }

        # 根据油液类型和温度确定影响
        if fluid_type == "FUEL":
            if temperature > 15:
                volatility = "高"
                viscosity = "低"
                cleanup_difficulty = "简单"
                time_factor = 0.8  # 挥发快，清理简化
            elif temperature < 0:
                volatility = "低"
                viscosity = "高"
                cleanup_difficulty = "困难"
                time_factor = 1.3  # 粘稠，清理难度增加
            else:
                volatility = "中"
                viscosity = "中"
                cleanup_difficulty = "中等"
                time_factor = 1.0

        elif fluid_type == "HYDRAULIC":
            # 液压油温度影响较小
            volatility = "低"
            if temperature < -5:
                viscosity = "高"
                cleanup_difficulty = "较难"
                time_factor = 1.1
            else:
                viscosity = "中"
                cleanup_difficulty = "中等"
                time_factor = 1.0

        else:  # OIL
            if temperature < -5:
                volatility = "极低"
                viscosity = "极高"
                cleanup_difficulty = "困难"
                time_factor = 1.5  # 凝固，清理困难
            else:
                volatility = "低"
                viscosity = "高"
                cleanup_difficulty = "中等"
                time_factor = 1.0

        return {
            "temperature_celsius": temperature,
            "volatility": volatility,
            "viscosity": viscosity,
            "cleanup_difficulty": cleanup_difficulty,
            "time_factor": time_factor
        }

    def _analyze_visibility_impact(self, weather: Dict[str, Any]) -> Dict[str, Any]:
        """分析能见度影响"""
        visibility = weather.get("visibility")
        if visibility is None:
            visibility = 10000  # 默认10km

        if visibility >= 10000:
            safety_level = "良好"
            require_extra_caution = False
            time_factor = 1.0
        elif visibility >= 5000:
            safety_level = "一般"
            require_extra_caution = False
            time_factor = 1.05
        else:
            safety_level = "困难"
            require_extra_caution = True
            time_factor = 1.15  # 需要额外照明

        return {
            "visibility_meters": visibility,
            "safety_level": safety_level,
            "require_extra_caution": require_extra_caution,
            "time_factor": time_factor
        }

    def _calculate_cleanup_adjustment(
        self,
        wind_impact: Dict,
        temperature_impact: Dict,
        visibility_impact: Dict,
        fluid_type: str
    ) -> Dict[str, Any]:
        """计算清理时间调整系数"""
        # 综合各因素的时间调整系数
        wind_factor = 1.0
        if wind_impact["wind_speed_ms"] > 5:
            wind_factor = 1.2  # 快速扩散，清理面积大

        temp_factor = temperature_impact.get("time_factor", 1.0)
        vis_factor = visibility_impact.get("time_factor", 1.0)

        # 总调整系数（乘法）
        total_factor = wind_factor * temp_factor * vis_factor

        return {
            "wind_factor": wind_factor,
            "temperature_factor": temp_factor,
            "visibility_factor": vis_factor,
            "total_factor": round(total_factor, 2)
        }

    def _wind_direction_to_text(self, degrees: float) -> str:
        """将风向角度转换为文字描述"""
        if degrees is None:
            return "未知"

        # 风向是"风来自的方向"，扩散是"风吹向的方向"（相反180度）
        spread_degrees = (degrees + 180) % 360

        directions = [
            "北", "东北", "东", "东南", "南", "西南", "西", "西北"
        ]
        index = int((spread_degrees + 22.5) / 45) % 8
        return directions[index] + "方向"

    def _format_observation(self, impact: Dict, weather: Dict) -> str:
        """格式化输出"""
        wind = impact["wind_impact"]
        temp = impact["temperature_impact"]
        vis = impact["visibility_impact"]
        adjust = impact["cleanup_time_adjustment"]

        lines = ["气象影响评估完成:"]

        # 风向风速
        lines.append(f"🌬️  风向: {wind['spread_direction']}, "
                    f"风速: {wind['wind_speed_ms']:.1f}m/s ({wind['spread_rate']}扩散)")

        # 温度
        temp_celsius = temp.get('temperature_celsius')
        if temp_celsius is not None:
            lines.append(f"🌡️  温度: {temp_celsius:.1f}°C, "
                        f"油液特性: 挥发性{temp['volatility']}/粘度{temp['viscosity']}, "
                        f"清理难度: {temp['cleanup_difficulty']}")

        # 能见度
        vis_km = vis['visibility_meters'] / 1000
        lines.append(f"👁️  能见度: {vis_km:.1f}km ({vis['safety_level']})")
        if vis['require_extra_caution']:
            lines.append("   ⚠️ 建议增加照明设备")

        # 清理时间调整
        lines.append(f"⏱️  清理时间调整系数: {adjust['total_factor']:.2f}")
        if adjust['total_factor'] > 1.1:
            lines.append("   （气象条件不利，清理时间延长）")
        elif adjust['total_factor'] < 0.9:
            lines.append("   （气象条件有利，清理时间缩短）")

        return "\n".join(lines)
