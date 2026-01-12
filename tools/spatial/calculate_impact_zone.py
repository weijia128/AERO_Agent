"""
影响范围计算工具 (Graph 推理)

对应文档方案的 P4 区域隔离
"""
from typing import Dict, Any, List, Set
from tools.base import BaseTool
from tools.spatial.topology_loader import get_topology_loader
from agent.state import risk_level_rank

# 扩散规则
SPREAD_RULES = {
    "FUEL": {
        "HIGH": {"radius": 3, "runway_impact": True},   # 高危燃油：3跳扩散，影响跑道
        "MEDIUM": {"radius": 2, "runway_impact": True}, # 中危燃油：2跳扩散
        "LOW": {"radius": 1, "runway_impact": False},   # 低危燃油：1跳扩散
    },
    "HYDRAULIC": {
        "HIGH": {"radius": 2, "runway_impact": False},
        "MEDIUM": {"radius": 1, "runway_impact": False},
        "LOW": {"radius": 1, "runway_impact": False},
    },
    "OIL": {
        "HIGH": {"radius": 1, "runway_impact": False},
        "MEDIUM": {"radius": 1, "runway_impact": False},
        "LOW": {"radius": 0, "runway_impact": False},
    },
}




class CalculateImpactZoneTool(BaseTool):
    """计算影响范围 (Graph 推理)"""
    
    name = "calculate_impact_zone"
    description = """基于机场拓扑图计算泄漏影响范围。

输入参数:
- position: 事发位置（停机位/滑行道）
- fluid_type: 油液类型 (FUEL/HYDRAULIC/OIL)
    - risk_level: 风险等级 (R1-R4)

返回信息:
- 隔离节点列表
- 受影响滑行道
- 受影响跑道
- 受影响航班预估"""
    
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 获取参数
        position = inputs.get("position", "")
        fluid_type = inputs.get("fluid_type", "FUEL")
        risk_level = inputs.get("risk_level", "R2")

        # 从状态获取默认值
        if not position:
            incident = state.get("incident", {})
            position = incident.get("position", "")
        if not fluid_type:
            incident = state.get("incident", {})
            fluid_type = incident.get("fluid_type", "FUEL")
        if not risk_level:
            risk = state.get("risk_assessment", {})
            risk_level = risk.get("level", "R2")

        if not position:
            return {"observation": "缺少位置信息，无法计算影响范围"}

        # 加载拓扑图
        topology = get_topology_loader()

        # 查找起始节点
        start_node_result = topology.find_nearest_node(position)
        if start_node_result is None:
            return {"observation": f"未在拓扑图中找到位置: {position}"}

        start_node_id, start_node_info = start_node_result

        # 获取扩散规则
        fluid_rules = SPREAD_RULES.get(fluid_type, SPREAD_RULES["FUEL"])
        rank = risk_level_rank(risk_level)
        if rank >= 3:
            normalized_level = "HIGH"
        elif rank == 2:
            normalized_level = "MEDIUM"
        elif rank == 1:
            normalized_level = "LOW"
        else:
            normalized_level = "MEDIUM"
        rule = fluid_rules.get(normalized_level, fluid_rules["MEDIUM"])

        # BFS 扩散计算（使用拓扑加载器的方法）
        isolated_nodes = topology.bfs_spread(start_node_id, rule["radius"])

        # 分类节点
        affected_taxiways = []
        affected_runways = []
        affected_stands = []

        for node_id in isolated_nodes:
            node = topology.get_node(node_id)
            if node:
                node_type = node.get('type')
                if node_type == 'taxiway':
                    affected_taxiways.append(node_id)
                elif node_type == 'runway':
                    affected_runways.append(node_id)
                elif node_type == 'stand':
                    affected_stands.append(node_id)

        # 检查跑道影响 - 如果受影响的滑行道连接到跑道
        if rule["runway_impact"]:
            for twy_id in affected_taxiways:
                adjacent = topology.get_adjacent_nodes(twy_id)
                for adj_id in adjacent:
                    adj_node = topology.get_node(adj_id)
                    if adj_node and adj_node.get('type') == 'runway':
                        if adj_id not in affected_runways:
                            affected_runways.append(adj_id)

        # TODO: 将在下一步实现基于真实航班计划的影响预测
        affected_flights = {}
        if affected_runways:
            affected_flights = {
                "待实现": "将基于历史航班数据预测"
            }

        # 构建结果
        observation = (
            f"影响范围分析完成（基于真实拓扑）: "
            f"起始节点={start_node_id}, "
            f"隔离区域={len(isolated_nodes)}个节点, "
            f"受影响机位={len(affected_stands)}个, "
            f"受影响滑行道={len(affected_taxiways)}个, "
            f"受影响跑道={len(affected_runways)}个"
        )

        return {
            "observation": observation,
            "spatial_analysis": {
                "anchor_node": start_node_id,
                "anchor_node_type": start_node_info.get('type'),
                "isolated_nodes": list(isolated_nodes),
                "affected_taxiways": affected_taxiways,
                "affected_runways": affected_runways,
                "affected_stands": affected_stands,
                "affected_flights": affected_flights,
                "impact_radius": rule["radius"],
            },
        }
