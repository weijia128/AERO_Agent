"""
漏油事故综合分析工具

集成气象影响、清理时间预估、空间影响分析、航班影响预测，并生成风险场景和解决建议。
所有数据来源：
- 航班计划：2026-01-06 08:00-12:00 真实数据
- 气象数据：2026-01-06 08:00-12:00 真实数据
- 机场拓扑：真实拓扑图数据
"""
import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from tools.base import BaseTool
from tools.assessment.assess_weather_impact import AssessWeatherImpactTool
from tools.assessment.estimate_cleanup_time import EstimateCleanupTimeTool
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool
from tools.spatial.predict_flight_impact import PredictFlightImpactTool
from config.llm_config import get_llm_client

logger = logging.getLogger(__name__)


class AnalyzeSpillComprehensiveTool(BaseTool):
    """漏油事故综合分析工具"""

    name = "analyze_spill_comprehensive"
    description = """执行漏油事故的完整分析，包括气象影响、清理时间、空间范围、航班影响、风险场景和解决建议。

输入参数:
- 所有参数从 AgentState 自动获取（position, fluid_type, leak_size, incident_time）

返回信息:
- 清理时间预估（含气象调整）
- 空间影响范围（受影响机位、滑行道、跑道）
- 受影响航班列表和统计
- 可能发生的风险场景
- 针对性解决建议"""

    def __init__(self):
        super().__init__()
        # 初始化子工具
        self.weather_tool = AssessWeatherImpactTool()
        self.cleanup_tool = EstimateCleanupTimeTool()
        self.impact_zone_tool = CalculateImpactZoneTool()
        self.flight_tool = PredictFlightImpactTool()

        # 导入位置影响分析工具
        from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool
        self.position_impact_tool = AnalyzePositionImpactTool()

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行综合分析"""

        # ============================================================
        # 第1步：提取事故信息
        # ============================================================
        incident = state.get("incident", {})

        position = incident.get("position")
        fluid_type = incident.get("fluid_type")
        # 修复：leak_size 变为可选（P2字段），缺失时使用 MEDIUM 默认值
        leak_size = incident.get("leak_size") or "MEDIUM"
        incident_time = incident.get("incident_time") or incident.get("start_time")

        # 验证必需字段（仅 P1 字段）
        missing_fields = []
        if not position:
            missing_fields.append("position（事发位置）")
        if not fluid_type:
            missing_fields.append("fluid_type（油液类型）")

        if missing_fields:
            return {
                "observation": f"缺少关键信息，无法执行综合分析: {', '.join(missing_fields)}\n"
                               f"请先补充这些信息。\n"
                               f"注意：leak_size（泄漏面积）为可选字段，缺失时将使用 MEDIUM 默认值。"
            }

        # 使用默认时间（2026-01-06 10:00，数据集时间范围内）
        if not incident_time:
            incident_time = "2026-01-06 10:00:00"
            incident["incident_time"] = incident_time

        # 获取风险等级（如果已评估）
        risk_assessment = state.get("risk_assessment", {})
        # 修复：正确读取风险等级，支持 R1-R4 和 HIGH/MEDIUM/LOW 两种格式
        risk_level_raw = risk_assessment.get("level") or risk_assessment.get("risk_level", "R2")
        risk_level = self._normalize_risk_level(risk_level_raw)

        # ============================================================
        # 第2步：气象影响评估
        # ============================================================
        weather_result = self.weather_tool.execute(state, {
            "position": position,
            "incident_time": incident_time,
            "fluid_type": fluid_type
        })

        weather_impact = weather_result.get("weather_impact", {})
        state["weather_impact"] = weather_impact

        # ============================================================
        # 第3步：清理时间预估
        # ============================================================
        cleanup_result = self.cleanup_tool.execute(state, {
            "fluid_type": fluid_type,
            "leak_size": leak_size,
            "position": position
        })

        # 修复：正确读取清理时间估算结果
        cleanup_estimate = cleanup_result.get("cleanup_time_estimate", {})
        cleanup_minutes = cleanup_estimate.get("adjusted_time_minutes", 60)
        base_time = cleanup_estimate.get("base_time_minutes", 60)

        # ============================================================
        # 第4步：空间影响分析
        # ============================================================
        impact_zone_result = self.impact_zone_tool.execute(state, {
            "position": position,
            "fluid_type": fluid_type,
            "risk_level": risk_level
        })

        spatial_analysis = impact_zone_result.get("spatial_analysis", {})
        state["spatial_analysis"] = spatial_analysis

        # ============================================================
        # 第4.5步：位置影响分析
        # ============================================================
        position_impact_result = self.position_impact_tool.execute(state, {
            "position": position,
            "fluid_type": fluid_type,
            "risk_level": risk_level
        })

        position_impact = position_impact_result.get("position_impact_analysis", {})

        # ============================================================
        # 第5步：航班影响预测
        # ============================================================
        # 计算分析时间窗口（清理时间 + 30分钟缓冲）
        time_window_hours = (cleanup_minutes + 30) / 60

        flight_result = self.flight_tool.execute(state, {
            "time_window": time_window_hours
        })

        flight_impact = flight_result.get("flight_impact", {})

        # ============================================================
        # 第6步：生成风险场景分析（整合位置影响数据）
        # ============================================================
        risk_scenarios = self._generate_risk_scenarios(
            position=position,
            fluid_type=fluid_type,
            leak_size=leak_size,
            risk_level=risk_level,
            spatial_analysis=spatial_analysis,
            flight_impact=flight_impact,
            cleanup_minutes=cleanup_minutes,
            position_impact=position_impact
        )

        # ============================================================
        # 第7步：生成解决建议（整合位置影响数据）
        # ============================================================
        recommendations = self._generate_recommendations(
            position=position,
            fluid_type=fluid_type,
            leak_size=leak_size,
            risk_level=risk_level,
            spatial_analysis=spatial_analysis,
            flight_impact=flight_impact,
            cleanup_minutes=cleanup_minutes,
            weather_impact=weather_impact,
            position_impact=position_impact
        )

        impact_narrative = self._generate_operational_impact_narrative(
            state=state,
            position=position,
            fluid_type=fluid_type,
            leak_size=leak_size,
            incident_time=incident_time,
            cleanup_minutes=cleanup_minutes,
            base_time=base_time,
            weather_impact=weather_impact,
            spatial_analysis=spatial_analysis,
            flight_impact=flight_impact,
            position_impact=position_impact,
            risk_level=risk_level,
        )
        command_dispatch_advice = self._generate_command_dispatch_advice(
            state=state,
            position=position,
            fluid_type=fluid_type,
            leak_size=leak_size,
            incident_time=incident_time,
            cleanup_minutes=cleanup_minutes,
            base_time=base_time,
            weather_impact=weather_impact,
            spatial_analysis=spatial_analysis,
            flight_impact=flight_impact,
            position_impact=position_impact,
            risk_level=risk_level,
        )

        # ============================================================
        # 生成综合观测结果（整合位置影响数据）
        # ============================================================
        observation = self._generate_comprehensive_observation(
            state=state,
            position=position,
            fluid_type=fluid_type,
            leak_size=leak_size,
            incident_time=incident_time,
            cleanup_minutes=cleanup_minutes,
            base_time=base_time,
            weather_impact=weather_impact,
            spatial_analysis=spatial_analysis,
            flight_impact=flight_impact,
            risk_scenarios=risk_scenarios,
            recommendations=recommendations,
            position_impact=position_impact,
            impact_narrative=impact_narrative,
            command_dispatch_advice=command_dispatch_advice,
        )

        return {
            "observation": observation,
            "spatial_analysis": spatial_analysis,
            "position_impact_analysis": position_impact,
            "flight_impact_prediction": flight_impact,
            "weather_impact": weather_impact,
            "cleanup_time_estimate": cleanup_estimate,
            "comprehensive_analysis": {
                "cleanup_analysis": {
                    "base_time_minutes": base_time,
                    "weather_adjusted_minutes": cleanup_minutes,
                    "weather_factors": weather_impact.get("cleanup_time_adjustment", {}),
                },
                "spatial_impact": {
                    "affected_stands": spatial_analysis.get("affected_stands", []),
                    "affected_taxiways": spatial_analysis.get("affected_taxiways", []),
                    "affected_runways": spatial_analysis.get("affected_runways", []),
                    "impact_radius_hops": spatial_analysis.get("impact_radius", 0),
                },
                "position_impact": position_impact,  # 🆕 新增：位置影响分析结果
                "flight_impact": {
                    "time_window": flight_impact.get("time_window", {}),
                    "affected_flights": flight_impact.get("affected_flights", []),
                    "statistics": flight_impact.get("statistics", {}),
                },
                "risk_scenarios": risk_scenarios,
                "recommendations": recommendations,
                "operational_impact_narrative": impact_narrative,
                "command_dispatch_advice": command_dispatch_advice,
            }
        }

    def _generate_risk_scenarios(
        self,
        position: str,
        fluid_type: str,
        leak_size: str,
        risk_level: str,
        spatial_analysis: Dict[str, Any],
        flight_impact: Dict[str, Any],
        cleanup_minutes: int,
        position_impact: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        生成可能发生的风险场景

        分析维度：
        1. 安全风险（火灾、爆炸）
        2. 运行风险（航班延误、容量下降）
        3. 扩散风险（污染范围扩大）
        """
        scenarios = []

        # 提取影响数据
        affected_stands = spatial_analysis.get("affected_stands", [])
        affected_runways = spatial_analysis.get("affected_runways", [])
        affected_taxiways = spatial_analysis.get("affected_taxiways", [])

        stats = flight_impact.get("statistics", {})
        total_flights = stats.get("total_affected_flights", 0)
        total_delay = stats.get("total_delay_minutes", 0)

        # 场景1：安全风险
        if fluid_type == "FUEL":
            if risk_level in ["HIGH", "CRITICAL"]:
                scenarios.append({
                    "category": "安全风险",
                    "scenario": "燃油泄漏引发火灾或爆炸",
                    "probability": "高" if risk_level == "CRITICAL" else "中",
                    "impact": "严重",
                    "description": (
                        f"燃油泄漏面积为{leak_size}，存在明火或静电引燃风险。"
                        f"如发生火灾，可能波及{len(affected_stands)}个机位，"
                        f"造成人员伤亡和设备损毁。"
                    )
                })
            else:
                scenarios.append({
                    "category": "安全风险",
                    "scenario": "燃油挥发造成空气污染",
                    "probability": "中",
                    "impact": "中等",
                    "description": (
                        f"燃油挥发可能对周边{len(affected_stands)}个机位的作业人员造成健康影响，"
                        f"需要加强通风和个人防护。"
                    )
                })

        # 场景2：运行风险
        if total_flights > 0:
            avg_delay = total_delay / total_flights if total_flights else 0

            if len(affected_runways) > 0:
                scenarios.append({
                    "category": "运行风险",
                    "scenario": "跑道封闭导致机场容量严重下降",
                    "probability": "高",
                    "impact": "严重",
                    "description": (
                        f"受影响跑道：{', '.join(affected_runways)}。"
                        f"预计{total_flights}架次航班受影响，"
                        f"平均延误{avg_delay:.0f}分钟，累计延误{total_delay}分钟。"
                        f"如果清理时间超过{cleanup_minutes}分钟，延误将进一步扩大。"
                    )
                })
            else:
                scenarios.append({
                    "category": "运行风险",
                    "scenario": "机位和滑行道封闭导致局部拥堵",
                    "probability": "中",
                    "impact": "中等",
                    "description": (
                        f"受影响机位：{len(affected_stands)}个，"
                        f"滑行道：{len(affected_taxiways)}条。"
                        f"预计{total_flights}架次航班需改机位或绕行，"
                        f"平均延误{avg_delay:.0f}分钟。"
                    )
                })
        elif position_impact:
            node_type = position_impact.get("node_type", "stand")
            scenarios.append({
                "category": "运行风险",
                "scenario": "局部设施受限导致运行效率下降",
                "probability": "中",
                "impact": "中等",
                "description": (
                    f"事故位置类型为{node_type}，需临时限制通行或封闭，"
                    "可能造成局部滑行瓶颈或机位调度压力上升。"
                )
            })

        # 场景3：扩散风险
        if leak_size == "LARGE" or len(affected_taxiways) > 3:
            scenarios.append({
                "category": "扩散风险",
                "scenario": "污染范围持续扩大",
                "probability": "中",
                "impact": "中等",
                "description": (
                    f"当前影响范围：{len(affected_stands)}个机位，"
                    f"{len(affected_taxiways)}条滑行道。"
                    f"如果清理不及时或遇降雨，污染可能沿滑行道进一步扩散，"
                    f"影响更多运行区域。"
                )
            })

        # 场景4：连锁反应
        if total_flights > 5:
            scenarios.append({
                "category": "连锁风险",
                "scenario": "航班大面积延误引发旅客滞留",
                "probability": "中",
                "impact": "中等",
                "description": (
                    f"{total_flights}架次航班延误可能导致数千名旅客滞留。"
                    f"如果延误时间超过2小时，需要安排临时住宿和餐饮，"
                    f"增加运营成本和旅客投诉。"
                )
            })

        return scenarios

    def _generate_recommendations(
        self,
        position: str,
        fluid_type: str,
        leak_size: str,
        risk_level: str,
        spatial_analysis: Dict[str, Any],
        flight_impact: Dict[str, Any],
        cleanup_minutes: int,
        weather_impact: Dict[str, Any],
        position_impact: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        生成针对性解决建议

        分类：
        1. 应急处置建议
        2. 运行调整建议
        3. 资源调度建议
        4. 旅客服务建议
        """
        recommendations = []

        # 提取数据
        affected_stands = spatial_analysis.get("affected_stands", [])
        affected_runways = spatial_analysis.get("affected_runways", [])
        affected_taxiways = spatial_analysis.get("affected_taxiways", [])

        stats = flight_impact.get("statistics", {})
        total_flights = stats.get("total_affected_flights", 0)
        affected_flights = flight_impact.get("affected_flights", [])

        # 建议1：应急处置
        if fluid_type == "FUEL" and risk_level in ["HIGH", "CRITICAL"]:
            recommendations.append({
                "category": "应急处置",
                "priority": "紧急",
                "action": "立即启动消防应急响应",
                "details": (
                    f"1. 立即通知消防部门到达{position}位置\n"
                    f"2. 设置{cleanup_minutes}米隔离区，禁止明火和车辆通行\n"
                    f"3. 疏散周边{len(affected_stands)}个机位的作业人员\n"
                    f"4. 准备泡沫灭火器和吸油毡，防止火灾和扩散"
                ),
                "estimated_time": "立即执行",
            })
        else:
            recommendations.append({
                "category": "应急处置",
                "priority": "高",
                "action": "启动环境保护措施",
                "details": (
                    f"1. 在{position}周边布设吸油毡和围油栏\n"
                    f"2. 防止污染物进入排水系统\n"
                    f"3. 通知环保部门和场务部门\n"
                    f"4. 准备清洗设备和清洁剂"
                ),
                "estimated_time": "15分钟内",
            })

        # 建议2：运行调整
        if len(affected_runways) > 0:
            # 跑道封闭
            runway_list = ", ".join(affected_runways)
            recommendations.append({
                "category": "运行调整",
                "priority": "紧急",
                "action": f"暂停{runway_list}跑道运行",
                "details": (
                    f"1. 立即发布NOTAM，通知{runway_list}跑道关闭约{cleanup_minutes}分钟\n"
                    f"2. 协调使用备用跑道（如有）\n"
                    f"3. 通知塔台和进近管制调整进离场程序\n"
                    f"4. 预计影响{total_flights}架次航班，提前通知航空公司"
                ),
                "estimated_time": f"{cleanup_minutes}分钟",
            })
        elif len(affected_stands) > 3:
            # 机位大面积封闭
            recommendations.append({
                "category": "运行调整",
                "priority": "高",
                "action": f"调整{len(affected_stands)}个机位的航班分配",
                "details": (
                    f"1. 受影响机位：{', '.join(affected_stands[:5])}等\n"
                    f"2. 协调{total_flights}架次航班改停备用机位\n"
                    f"3. 优先保障国际航班和宽体机停靠\n"
                    f"4. 启用远机位和摆渡车服务"
                ),
                "estimated_time": f"{cleanup_minutes}分钟",
            })
        else:
            # 局部调整
            recommendations.append({
                "category": "运行调整",
                "priority": "中",
                "action": f"调整{position}及周边机位使用",
                "details": (
                    f"1. 封闭{position}机位约{cleanup_minutes}分钟\n"
                    f"2. 引导{total_flights}架次航班使用相邻机位或滑行道绕行\n"
                    f"3. 通知塔台调整滑行路线"
                ),
                "estimated_time": f"{cleanup_minutes}分钟",
            })
        if position_impact:
            efficiency = position_impact.get("efficiency_impact", {})
            desc = efficiency.get("description")
            if desc:
                recommendations.append({
                    "category": "运行调整",
                    "priority": "中",
                    "action": "根据位置影响优化地面运行",
                    "details": (
                        f"1. 位置影响提示：{desc}\n"
                        f"2. 根据现场瓶颈调整滑行或机位分配策略"
                    ),
                    "estimated_time": "即时调整",
                })

        # 建议3：航班协调
        if total_flights > 0:
            # 分析航班类型
            high_priority_flights = [
                f for f in affected_flights
                if (f.get("estimated_delay_minutes") or 0) >= 60
            ]

            if len(high_priority_flights) > 0:
                recommendations.append({
                    "category": "航班协调",
                    "priority": "高",
                    "action": f"协调{len(high_priority_flights)}架次严重延误航班",
                    "details": (
                        f"1. 严重延误航班（≥60分钟）：\n" +
                        "\n".join([
                            f"   - {f['callsign']}: 预计延误{f['estimated_delay_minutes']}分钟"
                            for f in high_priority_flights[:3]
                        ]) +
                        f"\n2. 建议这些航班优先改用备用机位或跑道\n"
                        f"3. 通知航空公司提前安排旅客改签或等待"
                    ),
                    "estimated_time": "即时协调",
                })

        # 建议4：资源调度
        recommendations.append({
            "category": "资源调度",
            "priority": "中",
            "action": "调配清理设备和人员",
            "details": (
                f"1. 根据泄漏面积（{leak_size}）调配清理设备\n"
                f"2. 预计需要清理时间{cleanup_minutes}分钟\n"
                f"3. 安排清洗车、吸污车和人工清理队伍\n"
                f"4. 准备充足的吸油毡、清洁剂等消耗品"
            ),
            "estimated_time": f"{cleanup_minutes}分钟",
        })

        # 建议5：气象因素应对
        temp_impact = weather_impact.get("temperature_impact", {})
        temp_factor = temp_impact.get("time_factor") or 1.0

        if temp_factor > 1.1:
            recommendations.append({
                "category": "气象应对",
                "priority": "中",
                "action": "应对低温环境影响",
                "details": (
                    f"1. 当前温度导致清理时间延长{int((temp_factor - 1) * 100)}%\n"
                    f"2. 使用热水或加热清洁剂提高清洁效率\n"
                    f"3. 注意防冻，保护清洁设备\n"
                    f"4. 加强人员保暖措施"
                ),
                "estimated_time": "持续关注",
            })

        # 建议6：旅客服务（如果延误严重）
        avg_delay = stats.get("average_delay_minutes") or 0
        if total_flights > 5 or (total_flights > 0 and avg_delay > 45):
            recommendations.append({
                "category": "旅客服务",
                "priority": "中",
                "action": "加强旅客服务和信息发布",
                "details": (
                    f"1. 通过广播、显示屏和APP通知{total_flights}架次航班延误信息\n"
                    f"2. 在值机柜台和登机口安排服务人员解答旅客问题\n"
                    f"3. 提供免费饮水和休息区\n"
                    f"4. 对延误超过2小时的航班提供餐食补偿"
                ),
                "estimated_time": "持续服务",
            })

        return recommendations

    def _generate_comprehensive_observation(
        self,
        state: Dict[str, Any],
        position: str,
        fluid_type: str,
        leak_size: str,
        incident_time: str,
        cleanup_minutes: int,
        base_time: int,
        weather_impact: Dict[str, Any],
        spatial_analysis: Dict[str, Any],
        flight_impact: Dict[str, Any],
        risk_scenarios: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        position_impact: Dict[str, Any],
        impact_narrative: str,
        command_dispatch_advice: str,
    ) -> str:
        """生成综合观测结果（格式化输出）"""

        # 提取数据
        affected_stands = spatial_analysis.get("affected_stands", [])
        affected_runways = spatial_analysis.get("affected_runways", [])
        affected_taxiways = spatial_analysis.get("affected_taxiways", [])

        stats = flight_impact.get("statistics", {})
        total_flights = stats.get("total_affected_flights", 0)
        total_delay = stats.get("total_delay_minutes", 0)
        avg_delay = stats.get("average_delay_minutes", 0)

        cleanup_adj = weather_impact.get("cleanup_time_adjustment", {})
        total_factor = cleanup_adj.get("total_factor")
        if total_factor is None:
            total_factor = 1.0

        # 构建输出
        lines = []
        lines.append("=" * 80)
        lines.append("漏油事故综合分析报告")
        lines.append("=" * 80)

        # 基本信息
        lines.append("\n【事故基本信息】")
        lines.append(f"  位置: {position}")
        lines.append(f"  时间: {incident_time}")
        lines.append(f"  油液类型: {fluid_type}")
        lines.append(f"  泄漏面积: {leak_size}")

        # 清理时间
        lines.append("\n【清理时间预估】")
        lines.append(f"  基准清理时间: {base_time} 分钟")
        lines.append(f"  气象调整系数: {total_factor:.2f}")
        lines.append(f"  预估清理时间: {cleanup_minutes} 分钟")
        if abs(total_factor - 1.0) > 0.05:
            if total_factor > 1.0:
                lines.append(f"  ⚠️  气象条件不利，清理时间延长 {int((total_factor - 1) * 100)}%")
            else:
                lines.append(f"  ✓ 气象条件有利，清理时间缩短 {int((1 - total_factor) * 100)}%")

        # 空间影响
        lines.append("\n【空间影响范围】")
        lines.append(f"  受影响机位: {len(affected_stands)} 个")
        if len(affected_stands) > 0:
            lines.append(f"    → {', '.join(affected_stands[:10])}" +
                        ("..." if len(affected_stands) > 10 else ""))

        lines.append(f"  受影响滑行道: {len(affected_taxiways)} 条")
        if len(affected_taxiways) > 0:
            lines.append(f"    → {', '.join(affected_taxiways[:10])}" +
                        ("..." if len(affected_taxiways) > 10 else ""))

        lines.append(f"  受影响跑道: {len(affected_runways)} 条")
        if len(affected_runways) > 0:
            lines.append(f"    → {', '.join(affected_runways)}")

        # 位置影响
        if position_impact:
            lines.append("\n【位置影响分析】")
            node_id = position_impact.get("node_id", "未知")
            node_type = position_impact.get("node_type", "未知")
            direct = position_impact.get("direct_impact", {})
            impact_desc = direct.get("impact_description")
            lines.append(f"  位置节点: {node_id} ({node_type})")
            if impact_desc:
                lines.append(f"  影响描述: {impact_desc}")

        # 航班影响
        lines.append("\n【航班影响预测】")

        # 检查是否基于参考航班
        reference_flight = position_impact.get("reference_flight") if isinstance(position_impact, dict) else None
        if not reference_flight:
            reference_flight = state.get("reference_flight", {})

        if reference_flight and reference_flight.get("callsign"):
            callsign = reference_flight.get("callsign")
            ref_time = reference_flight.get("reference_time", "")
            lines.append(f"  参考航班: {callsign}")
            if ref_time:
                lines.append(f"  参考时间: {ref_time}")

        time_window = flight_impact.get("time_window", {})
        start_time = time_window.get("start", "")
        end_time = time_window.get("end", "")

        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
                lines.append(f"  分析时间窗口: {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}")
            except (ValueError, TypeError) as e:
                logger.debug(f"解析时间窗口失败: {e}")
                lines.append(f"  分析时间窗口: {start_time} - {end_time}")

        lines.append(f"  受影响航班: {total_flights} 架次")
        lines.append(f"  累计延误时间: {total_delay} 分钟")
        if total_flights > 0:
            lines.append(f"  平均延误: {avg_delay:.1f} 分钟/架次")

        sev = stats.get("severity_distribution", {})
        lines.append(f"  延误分布:")
        lines.append(f"    - 严重 (≥60分钟): {sev.get('high', 0)} 架次")
        lines.append(f"    - 中等 (20-59分钟): {sev.get('medium', 0)} 架次")
        lines.append(f"    - 轻微 (<20分钟): {sev.get('low', 0)} 架次")

        if impact_narrative:
            lines.append("\n【运行影响解读】")
            lines.append(impact_narrative.strip())

        if command_dispatch_advice:
            lines.append("\n【指挥调度建议】")
            lines.append(command_dispatch_advice.strip())

        # 风险场景
        lines.append("\n【可能发生的情况】")
        for i, scenario in enumerate(risk_scenarios, 1):
            lines.append(f"\n  场景 {i}: {scenario['scenario']}")
            lines.append(f"    类别: {scenario['category']}")
            lines.append(f"    发生概率: {scenario['probability']}")
            lines.append(f"    影响程度: {scenario['impact']}")
            lines.append(f"    描述: {scenario['description']}")

        # 解决建议
        lines.append("\n【解决建议】")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"\n  建议 {i}: {rec['action']}")
            lines.append(f"    类别: {rec['category']}")
            lines.append(f"    优先级: {rec['priority']}")
            lines.append(f"    详细措施:")
            for detail_line in rec['details'].split('\n'):
                lines.append(f"      {detail_line}")
            lines.append(f"    预计耗时: {rec['estimated_time']}")

        lines.append("\n" + "=" * 80)
        lines.append("分析完成 | 数据来源: 2026-01-06 真实历史数据")
        lines.append("=" * 80)

        return "\n".join(lines)

    def _generate_operational_impact_narrative(
        self,
        state: Dict[str, Any],
        position: str,
        fluid_type: str,
        leak_size: str,
        incident_time: str,
        cleanup_minutes: int,
        base_time: int,
        weather_impact: Dict[str, Any],
        spatial_analysis: Dict[str, Any],
        flight_impact: Dict[str, Any],
        position_impact: Dict[str, Any],
        risk_level: str,
    ) -> str:
        payload = {
            "incident": {
                "position": position,
                "fluid_type": fluid_type,
                "leak_size": leak_size,
                "incident_time": incident_time,
                "risk_level": risk_level,
            },
            "cleanup": {
                "base_minutes": base_time,
                "adjusted_minutes": cleanup_minutes,
                "weather_adjustment": weather_impact.get("cleanup_time_adjustment", {}),
            },
            "spatial_impact": {
                "affected_stands_count": len(spatial_analysis.get("affected_stands", [])),
                "affected_taxiways_count": len(spatial_analysis.get("affected_taxiways", [])),
                "affected_runways": spatial_analysis.get("affected_runways", []),
            },
            "position_impact": position_impact.get("direct_impact", {}),
            "flight_impact": {
                "time_window": flight_impact.get("time_window", {}),
                "statistics": flight_impact.get("statistics", {}),
                "top_affected_flights": [
                    {
                        "callsign": f.get("callsign"),
                        "type": f.get("type"),
                        "estimated_delay_minutes": f.get("estimated_delay_minutes"),
                        "stand": f.get("stand"),
                        "runway": f.get("runway"),
                    }
                    for f in (flight_impact.get("affected_flights", []) or [])[:5]
                ],
            },
        }

        reference_flight = state.get("reference_flight", {})
        if reference_flight:
            payload["reference_flight"] = {
                "callsign": reference_flight.get("callsign"),
                "reference_time": reference_flight.get("reference_time"),
                "stand": reference_flight.get("stand"),
                "runway": reference_flight.get("runway"),
            }

        prompt = (
            "你是机场运行影响分析助手。请基于以下结构化数据输出“运行影响解读”。\n"
            "要求：\n"
            "1) 只基于提供的数据，不新增事实或假设。\n"
            "2) 重点解释对运行能力、跑道/滑行/机位、航班延误和恢复时间的影响。\n"
            "3) 输出 4-6 句中文，客观克制，禁止建议或处置动作。\n"
            "4) 如果数据不足，请明确说明“影响评估受限”。\n"
            "只输出正文文本，不要标题。\n\n"
            f"结构化数据:\n{json.dumps(payload, ensure_ascii=False)}"
        )

        try:
            llm = get_llm_client()
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as exc:
            logger.warning("运行影响解读生成失败: %s", exc)
            return ""

    def _generate_command_dispatch_advice(
        self,
        state: Dict[str, Any],
        position: str,
        fluid_type: str,
        leak_size: str,
        incident_time: str,
        cleanup_minutes: int,
        base_time: int,
        weather_impact: Dict[str, Any],
        spatial_analysis: Dict[str, Any],
        flight_impact: Dict[str, Any],
        position_impact: Dict[str, Any],
        risk_level: str,
    ) -> str:
        payload = {
            "incident": {
                "position": position,
                "fluid_type": fluid_type,
                "leak_size": leak_size,
                "incident_time": incident_time,
                "risk_level": risk_level,
            },
            "cleanup": {
                "base_minutes": base_time,
                "adjusted_minutes": cleanup_minutes,
                "weather_adjustment": weather_impact.get("cleanup_time_adjustment", {}),
            },
            "spatial_impact": {
                "affected_stands_count": len(spatial_analysis.get("affected_stands", [])),
                "affected_taxiways_count": len(spatial_analysis.get("affected_taxiways", [])),
                "affected_runways": spatial_analysis.get("affected_runways", []),
            },
            "position_impact": position_impact.get("direct_impact", {}),
            "flight_impact": {
                "time_window": flight_impact.get("time_window", {}),
                "statistics": flight_impact.get("statistics", {}),
                "top_affected_flights": [
                    {
                        "callsign": f.get("callsign"),
                        "type": f.get("type"),
                        "estimated_delay_minutes": f.get("estimated_delay_minutes"),
                        "stand": f.get("stand"),
                        "runway": f.get("runway"),
                    }
                    for f in (flight_impact.get("affected_flights", []) or [])[:5]
                ],
            },
        }

        reference_flight = state.get("reference_flight", {})
        if reference_flight:
            payload["reference_flight"] = {
                "callsign": reference_flight.get("callsign"),
                "reference_time": reference_flight.get("reference_time"),
                "stand": reference_flight.get("stand"),
                "runway": reference_flight.get("runway"),
            }

        prompt = (
            "你是机场运行指挥调度助手。请基于以下结构化数据给出“指挥调度建议”。\n"
            "要求：\n"
            "1) 只基于提供的数据，不新增事实或假设。\n"
            "2) 建议聚焦跑道/滑行/机位调度、航班流量与放行顺序、资源协同与信息发布。\n"
            "3) 输出 3-5 条中文建议，每条单独一行，禁止标题、不要编号前缀。\n"
            "4) 如果数据不足，请输出一条：影响评估受限，建议继续补充现场数据。\n"
            "只输出正文文本。\n\n"
            f"结构化数据:\n{json.dumps(payload, ensure_ascii=False)}"
        )

        try:
            llm = get_llm_client()
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as exc:
            logger.warning("指挥调度建议生成失败: %s", exc)
            return ""
    def _normalize_risk_level(self, risk_level_raw: str) -> str:
        """
        标准化风险等级

        支持两种格式：
        - R1/R2/R3/R4（油污风险评估输出）
        - LOW/MEDIUM/HIGH/CRITICAL（其他场景）

        统一映射为：HIGH/MEDIUM/LOW/CRITICAL
        """
        if not risk_level_raw:
            return "MEDIUM"

        risk_str = str(risk_level_raw).upper()

        # R1-R4 映射
        risk_mapping = {
            "R1": "LOW",
            "R2": "MEDIUM",
            "R3": "HIGH",
            "R4": "CRITICAL"
        }

        # 如果是 R1-R4 格式，转换
        if risk_str in risk_mapping:
            return risk_mapping[risk_str]

        # 如果已经是标准格式，直接返回
        if risk_str in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            return risk_str

        # 默认返回 MEDIUM
        return "MEDIUM"


# 导出工具类
__all__ = ["AnalyzeSpillComprehensiveTool"]
