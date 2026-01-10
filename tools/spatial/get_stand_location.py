"""
停机位位置查询工具
"""
from typing import Dict, Any, List
from tools.base import BaseTool
from tools.spatial.topology_loader import get_topology_loader


class GetStandLocationTool(BaseTool):
    """获取停机位位置和周边信息"""
    
    name = "get_stand_location"
    description = """获取停机位的位置信息和周边设施。
    
输入参数:
- stand_id: 停机位编号（如 501）
- taxiway: 滑行道名称（如 A3）

返回信息:
- 坐标、相邻滑行道、最近跑道、消防站距离等"""
    
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        stand_id = inputs.get("stand_id", "")
        taxiway = inputs.get("taxiway", "")

        # 尝试从 incident 获取位置
        if not stand_id and not taxiway:
            incident = state.get("incident", {})
            position = incident.get("position", "")
            # 尝试判断是机位还是滑行道
            stand_id = position
            taxiway = position

        # 加载拓扑图
        topology = get_topology_loader()

        # 优先查找机位
        if stand_id:
            stand_info = topology.get_stand_info(stand_id)
            if stand_info:
                observation = (
                    f"停机位 {stand_info['id']} 信息（基于真实拓扑）: "
                    f"坐标=({stand_info['lat']:.5f}, {stand_info['lon']:.5f}), "
                    f"相邻滑行道={stand_info['adjacent_taxiways']}, "
                    f"最近跑道={stand_info['nearest_runway']}, "
                    f"观测次数={stand_info['observations']}, "
                    f"平均停留时间={stand_info['avg_dwell_time']:.0f}秒"
                )
                return {
                    "observation": observation,
                    "spatial_analysis": {
                        "anchor_node": stand_info['id'],
                        "stand_info": stand_info,
                    },
                }

        # 查找滑行道
        if taxiway:
            node_result = topology.find_nearest_node(taxiway, node_type='taxiway')
            if node_result:
                node_id, node_info = node_result
                adjacent = topology.get_adjacent_nodes(node_id)
                observation = (
                    f"滑行道 {node_id} 信息（基于真实拓扑）: "
                    f"坐标=({node_info['lat']:.5f}, {node_info['lon']:.5f}), "
                    f"连接节点={list(adjacent)}"
                )
                return {
                    "observation": observation,
                    "spatial_analysis": {
                        "anchor_node": node_id,
                        "taxiway_info": {
                            "id": node_id,
                            "lat": node_info['lat'],
                            "lon": node_info['lon'],
                            "connects": list(adjacent)
                        },
                    },
                }

        # 最后尝试模糊匹配任意节点
        position = stand_id or taxiway
        if position:
            node_result = topology.find_nearest_node(position)
            if node_result:
                node_id, node_info = node_result
                observation = (
                    f"位置 {position} 匹配到节点 {node_id} "
                    f"(类型={node_info['type']}, "
                    f"坐标=({node_info['lat']:.5f}, {node_info['lon']:.5f}))"
                )
                return {
                    "observation": observation,
                    "spatial_analysis": {
                        "anchor_node": node_id,
                        "node_info": node_info,
                    },
                }

        return {
            "observation": f"未在拓扑图中找到位置信息: {stand_id or taxiway}",
        }
