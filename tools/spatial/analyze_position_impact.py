"""
位置特定影响分析工具

根据漏油发生的位置类型（机位/滑行道/跑道），分析对机场运行的精细化影响
"""
from typing import Dict, Any, List, Set, Optional
from tools.base import BaseTool
from tools.spatial.topology_loader import get_topology_loader
from agent.state import risk_level_rank


# 位置影响规则配置
POSITION_IMPACT_RULES = {
    "runway": {
        "severity_multiplier": 3.0,  # 跑道漏油影响最严重
        "closure_time_minutes": {
            "FUEL": 120,      # 燃油需要2小时清理
            "HYDRAULIC": 60,  # 液压油1小时
            "OIL": 90         # 滑油1.5小时
        },
        "impact_description": {
            "FUEL": "跑道燃油泄漏属于极高风险事件，需立即关闭跑道进行泡沫覆盖和清理",
            "HYDRAULIC": "跑道液压油泄漏需封闭清理，期间航班无法起降",
            "OIL": "跑道滑油泄漏影响制动性能，需彻底清理后恢复运行"
        },
        "operational_impact": [
            "跑道关闭期间所有起降航班受阻",
            "启用备用跑道（如可用）",
            "空中航班可能需要盘旋等待或备降",
            "地面航班无法推出起飞"
        ]
    },
    "taxiway": {
        "severity_multiplier": 1.5,
        "closure_time_minutes": {
            "FUEL": 60,
            "HYDRAULIC": 45,
            "OIL": 30
        },
        "impact_description": {
            "FUEL": "滑行道燃油泄漏需封闭清理，航班需绕行",
            "HYDRAULIC": "滑行道液压油泄漏需清理，存在滑倒风险",
            "OIL": "滑行道滑油泄漏影响车辆通行，需清理"
        },
        "operational_impact": [
            "受影响滑行道封闭，航班需绕行",
            "地面滑行时间增加15-30分钟",
            "可能导致跑道入口排队",
            "机位推出可能受影响"
        ]
    },
    "stand": {
        "severity_multiplier": 1.0,
        "closure_time_minutes": {
            "FUEL": 90,
            "HYDRAULIC": 60,
            "OIL": 45
        },
        "impact_description": {
            "FUEL": "机位燃油泄漏属于高风险事件，本机位及相邻机位需撤离",
            "HYDRAULIC": "机位液压油泄漏需专业清理",
            "OIL": "机位滑油泄漏需清理，可继续使用邻近机位"
        },
        "operational_impact": [
            "本机位暂时无法使用",
            "相邻机位可能受影响（视风向和泄漏程度）",
            "原计划停靠该机位的航班需重新分配机位",
            "机位分配调度压力增加"
        ]
    }
}


# 效率降低评估规则
EFFICIENCY_IMPACT = {
    "runway": {
        "single_runway_airport": {
            "delay_per_flight": 45,  # 每架次延误45分钟
            "capacity_reduction": 0.8,  # 容量降低80%
            "description": "单跑道机场关闭将导致几乎完全停摆"
        },
        "multi_runway_airport": {
            "delay_per_flight": 15,
            "capacity_reduction": 0.3,
            "description": "多跑道机场可使用备用跑道，但仍影响30%容量"
        }
    },
    "taxiway": {
        "critical_taxiway": {
            "delay_per_flight": 20,
            "bottleneck_risk": "high",
            "description": "关键滑行道（连接机坪与跑道）封闭将造成瓶颈"
        },
        "normal_taxiway": {
            "delay_per_flight": 10,
            "bottleneck_risk": "medium",
            "description": "普通滑行道封闭影响相对较小"
        }
    },
    "stand": {
        "high_traffic_stand": {
            "gate_relocation_delay": 30,
            "description": "高使用率机位关闭需重新分配多个航班"
        },
        "normal_stand": {
            "gate_relocation_delay": 15,
            "description": "普通机位关闭影响有限"
        }
    }
}


def _normalize_risk_level(level: str) -> str:
    """将 R1-R4 映射为内部高/中/低标签。"""
    rank = risk_level_rank(level)
    if rank >= 3:
        return "HIGH"
    if rank == 2:
        return "MEDIUM"
    if rank == 1:
        return "LOW"
    return "MEDIUM"


class AnalyzePositionImpactTool(BaseTool):
    """位置特定影响分析工具"""

    name = "analyze_position_impact"
    description = """分析漏油发生在特定位置（机位/滑行道/跑道）对机场运行的精细化影响。

输入参数:
- position: 事发位置（自动从状态获取）
- fluid_type: 油液类型（自动从状态获取）
- risk_level: 风险等级（自动从状态获取，R1-R4）

返回信息:
- 位置类型和影响严重程度
- 设施封闭时间预估
- 运行效率降低评估
- 相邻设施影响分析
- 针对性处置建议"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 从状态获取信息
        incident = state.get("incident", {})
        position = incident.get("position", "")
        fluid_type = incident.get("fluid_type", "FUEL")
        risk_level = state.get("risk_assessment", {}).get("level", "R2")
        normalized_risk = _normalize_risk_level(risk_level)

        if not position:
            return {"observation": "缺少位置信息，无法进行位置影响分析"}

        # 加载拓扑图
        topology = get_topology_loader()

        # 查找位置节点
        node_result = topology.find_nearest_node(position)
        if node_result is None:
            return {"observation": f"未在拓扑图中找到位置: {position}"}

        node_id, node_info = node_result
        node_type = node_info.get('type', 'stand')

        # 获取影响规则
        type_rules = POSITION_IMPACT_RULES.get(node_type, {})
        if not type_rules:
            return {"observation": f"未知的位置类型: {node_type}"}

        # 获取相邻节点
        adjacent_nodes = topology.get_adjacent_nodes(node_id)

        # 分析直接影响
        direct_impact = self._analyze_direct_impact(
            node_id, node_type, node_info, fluid_type, normalized_risk, type_rules
        )

        # 分析相邻影响
        adjacent_impact = self._analyze_adjacent_impact(
            node_id, node_type, adjacent_nodes, fluid_type, topology
        )

        # 分析运行效率影响
        efficiency_impact = self._analyze_efficiency_impact(
            node_type, node_id, adjacent_nodes, topology
        )

        # 生成处置建议
        recommendations = self._generate_recommendations(
            node_type, fluid_type, normalized_risk, direct_impact, adjacent_impact
        )

        # 生成观测结果
        observation = self._generate_observation(
            node_id, node_type, fluid_type, risk_level,
            direct_impact, adjacent_impact, efficiency_impact, recommendations
        )

        return {
            "observation": observation,
            "position_impact_analysis": {
                "node_id": node_id,
                "node_type": node_type,
                "fluid_type": fluid_type,
                "risk_level": risk_level,
                "direct_impact": direct_impact,
                "adjacent_impact": adjacent_impact,
                "efficiency_impact": efficiency_impact,
                "recommendations": recommendations
            }
        }

    def _analyze_direct_impact(
        self,
        node_id: str,
        node_type: str,
        node_info: Dict,
        fluid_type: str,
        risk_level: str,
        type_rules: Dict
    ) -> Dict[str, Any]:
        """分析直接影响"""
        # 获取封闭时间
        base_closure_time = type_rules["closure_time_minutes"].get(fluid_type, 60)

        # 根据风险等级调整
        risk_multiplier = {
            "HIGH": 1.5,
            "MEDIUM": 1.0,
            "LOW": 0.7
        }.get(risk_level, 1.0)

        estimated_closure_time = int(base_closure_time * risk_multiplier)

        # 严重程度
        severity = type_rules["severity_multiplier"]
        severity *= risk_multiplier

        return {
            "facility_type": node_type,
            "facility_name": node_id,
            "affected_facility": self._get_facility_name_zh(node_type),
            "closure_time_minutes": estimated_closure_time,
            "severity_score": round(severity, 2),
            "impact_description": type_rules["impact_description"].get(fluid_type, ""),
            "operational_impacts": type_rules["operational_impact"]
        }

    def _analyze_adjacent_impact(
        self,
        node_id: str,
        node_type: str,
        adjacent_nodes: Set[str],
        fluid_type: str,
        topology
    ) -> Dict[str, Any]:
        """分析相邻设施影响"""
        if not adjacent_nodes:
            return {
                "total_adjacent": 0,
                "affected_adjacent": [],
                "by_type": {
                    "机位": [],
                    "滑行道": [],
                    "跑道": []
                },
                "count_by_type": {
                    "机位": 0,
                    "滑行道": 0,
                    "跑道": 0
                }
            }

        affected = []
        by_type = {
            "stand": [],
            "taxiway": [],
            "runway": []
        }

        for adj_id in adjacent_nodes:
            adj_node = topology.get_node(adj_id)
            if adj_node:
                adj_type = adj_node.get('type')
                if adj_type in by_type:
                    by_type[adj_type].append(adj_id)
                    affected.append({
                        "id": adj_id,
                        "type": adj_type,
                        "name_zh": self._get_facility_name_zh(adj_type)
                    })

        # 根据油液类型和位置类型判断影响范围
        spread_radius = {
            ("runway", "FUEL"): 2,  # 跑道燃油泄漏影响2跳
            ("runway", "HYDRAULIC"): 1,
            ("runway", "OIL"): 1,
            ("taxiway", "FUEL"): 1,  # 滑行道燃油泄漏影响1跳
            ("taxiway", "HYDRAULIC"): 1,
            ("taxiway", "OIL"): 0,
            ("stand", "FUEL"): 1,  # 机位燃油泄漏影响1跳
            ("stand", "HYDRAULIC"): 0,
            ("stand", "OIL"): 0,
        }.get((node_type, fluid_type), 0)

        # 如果有扩散半径，通过BFS获取更多受影响节点
        additional_affected = []
        if spread_radius > 0:
            spread_nodes = topology.bfs_spread(node_id, spread_radius)
            # 移除起始节点和直接相邻节点
            additional_nodes = spread_nodes - {node_id} - set(adjacent_nodes)
            for add_id in additional_nodes:
                add_node = topology.get_node(add_id)
                if add_node:
                    add_type = add_node.get('type')
                    if add_type in by_type:
                        by_type[add_type].append(add_id)

        return {
            "total_adjacent": len(adjacent_nodes),
            "directly_affected": len(affected),
            "spread_radius": spread_radius,
            "affected_adjacent": affected,
            "by_type": {
                "机位": by_type["stand"],
                "滑行道": by_type["taxiway"],
                "跑道": by_type["runway"]
            },
            "count_by_type": {
                "机位": len(by_type["stand"]),
                "滑行道": len(by_type["taxiway"]),
                "跑道": len(by_type["runway"])
            }
        }

    def _analyze_efficiency_impact(
        self,
        node_type: str,
        node_id: str,
        adjacent_nodes: Set[str],
        topology
    ) -> Dict[str, Any]:
        """分析运行效率影响"""
        if node_type == "runway":
            # 检查是否为单跑道机场
            all_runways = topology.get_nodes_by_type('runway')
            is_single_runway = len(all_runways) <= 1

            if is_single_runway:
                return {
                    "impact_type": "single_runway_airport",
                    "delay_per_flight": 45,
                    "capacity_reduction_percent": 80,
                    "description": "单跑道机场关闭将导致严重延误",
                    "details": [
                        "所有起降航班受阻",
                        "预计延误45分钟/架次",
                        "容量降低80%",
                        "建议航班备降其他机场"
                    ]
                }
            else:
                return {
                    "impact_type": "multi_runway_airport",
                    "delay_per_flight": 15,
                    "capacity_reduction_percent": 30,
                    "description": "可使用备用跑道，但仍影响运行效率",
                    "details": [
                        "启用备用跑道",
                        "预计延误15分钟/架次",
                        "容量降低30%",
                        "起降间隔可能需要增大"
                    ]
                }

        elif node_type == "taxiway":
            # 判断是否为关键滑行道（连接到跑道）
            connects_to_runway = False
            for adj_id in adjacent_nodes:
                adj_node = topology.get_node(adj_id)
                if adj_node and adj_node.get('type') == 'runway':
                    connects_to_runway = True
                    break

            if connects_to_runway:
                return {
                    "impact_type": "critical_taxiway",
                    "delay_per_flight": 20,
                    "bottleneck_risk": "high",
                    "description": "关键滑行道封闭，连接机坪与跑道",
                    "details": [
                        "滑行时间增加20分钟/架次",
                        "可能造成跑道入口排队",
                        "建议启用备用滑行路线"
                    ]
                }
            else:
                return {
                    "impact_type": "normal_taxiway",
                    "delay_per_flight": 10,
                    "bottleneck_risk": "medium",
                    "description": "普通滑行道封闭，影响有限",
                    "details": [
                        "滑行时间增加10分钟/架次",
                        "可通过其他滑行道绕行"
                    ]
                }

        elif node_type == "stand":
            # 检查机位使用频率
            node_info = topology.get_node(node_id)
            observations = node_info.get('observations', 0) if node_info else 0

            is_high_traffic = observations > 15  # 观测次数超过15次视为高使用率

            if is_high_traffic:
                return {
                    "impact_type": "high_traffic_stand",
                    "gate_relocation_delay": 30,
                    "description": f"高使用率机位（观测{observations}次），关闭影响较大",
                    "details": [
                        "机位重新分配延误约30分钟",
                        "影响多航班停靠计划",
                        "调度压力增加"
                    ]
                }
            else:
                return {
                    "impact_type": "normal_stand",
                    "gate_relocation_delay": 15,
                    "description": f"普通机位（观测{observations}次），影响相对较小",
                    "details": [
                        "机位重新分配延误约15分钟",
                        "影响有限"
                    ]
                }

        return {
            "impact_type": "unknown",
            "description": "未知的位置类型影响"
        }

    def _generate_recommendations(
        self,
        node_type: str,
        fluid_type: str,
        risk_level: str,
        direct_impact: Dict,
        adjacent_impact: Dict
    ) -> List[str]:
        """生成处置建议"""
        recommendations = []

        # 基于位置类型的建议
        if node_type == "runway":
            recommendations.extend([
                "立即通知塔台，关闭受影响跑道",
                "启用备用跑道（如可用）",
                "空中航班可能需要盘旋等待或备降",
                "地面航班暂停推出"
            ])

            if fluid_type == "FUEL":
                recommendations.extend([
                    "立即派遣消防车辆到现场",
                    "使用泡沫覆盖泄漏区域",
                    "清理期间严禁任何人员车辆进入"
                ])

        elif node_type == "taxiway":
            recommendations.extend([
                "设置警示标志，封闭受影响滑行道",
                "引导航班使用备用滑行路线",
                "增加地面引导人员"
            ])

            if fluid_type == "FUEL":
                recommendations.append("通知消防部门待命")

        elif node_type == "stand":
            recommendations.extend([
                "撤离本机位航空器（如未离开）",
                "封闭本机位及相邻机位",
                "重新分配受影响航班到其他机位"
            ])

            if fluid_type == "FUEL":
                recommendations.extend([
                    "通知消防部门立即到场",
                    "对相邻机位航空器进行防护"
                ])

        # 基于风险等级的建议
        if risk_level == "HIGH":
            recommendations.append("建议发布机场通告，告知航班延误情况")

        return recommendations

    def _get_facility_name_zh(self, facility_type: str) -> str:
        """获取设施类型中文名称"""
        mapping = {
            "runway": "跑道",
            "taxiway": "滑行道",
            "stand": "机位"
        }
        return mapping.get(facility_type, facility_type)

    def _generate_observation(
        self,
        node_id: str,
        node_type: str,
        fluid_type: str,
        risk_level: str,
        direct_impact: Dict,
        adjacent_impact: Dict,
        efficiency_impact: Dict,
        recommendations: List[str]
    ) -> str:
        """生成观测结果"""
        fluid_name = {
            "FUEL": "燃油",
            "HYDRAULIC": "液压油",
            "OIL": "滑油"
        }.get(fluid_type, fluid_type)

        facility_name = self._get_facility_name_zh(node_type)

        observation = (
            f"位置影响分析完成:\n\n"
            f"【事件位置】{node_id} ({facility_name})\n"
            f"【油液类型】{fluid_name}\n"
            f"【风险等级】{risk_level}\n\n"
        )

        # 直接影响
        observation += (
            f"【直接影响评估】\n"
            f"影响描述: {direct_impact.get('impact_description', '评估中')}\n"
            f"预计封闭时间: {direct_impact.get('closure_time_minutes', 0)} 分钟\n"
            f"严重程度评分: {direct_impact.get('severity_score', 0)}/5.0\n"
        )

        # 相邻影响
        observation += (
            f"\n【相邻设施影响】\n"
            f"直接相邻设施: {adjacent_impact.get('total_adjacent', 0)} 个\n"
        )
        count_by_type = adjacent_impact.get('count_by_type', {})
        if count_by_type.get('机位', 0) > 0:
            observation += f"  - 受影响机位: {count_by_type['机位']} 个\n"
        if count_by_type.get('滑行道', 0) > 0:
            observation += f"  - 受影响滑行道: {count_by_type['滑行道']} 条\n"
        if count_by_type.get('跑道', 0) > 0:
            observation += f"  - 受影响跑道: {count_by_type['跑道']} 条\n"

        # 运行效率影响
        observation += (
            f"\n【运行效率影响】\n"
            f"{efficiency_impact.get('description', '评估中')}\n"
        )
        if 'delay_per_flight' in efficiency_impact:
            observation += f"预计延误: {efficiency_impact['delay_per_flight']} 分钟/架次\n"
        if 'capacity_reduction_percent' in efficiency_impact:
            observation += f"容量降低: {efficiency_impact['capacity_reduction_percent']}%\n"

        # 处置建议
        observation += "\n【处置建议】\n"
        for i, rec in enumerate(recommendations[:5], 1):  # 最多显示5条
            observation += f"{i}. {rec}\n"

        return observation.strip()
