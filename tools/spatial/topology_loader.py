"""
机场拓扑图加载器

从基于轨迹聚类生成的拓扑图文件中加载真实机场拓扑数据
"""
import json
import os
from typing import Dict, Any, List, Set, Optional, Tuple, cast
from collections import defaultdict


class TopologyLoader:
    """拓扑图加载器"""

    def __init__(self, topology_file: Optional[str] = None):
        """
        初始化拓扑加载器

        Args:
            topology_file: 拓扑图JSON文件路径，如果为None则使用默认路径
        """
        if topology_file is None:
            env_override = os.getenv("AERO_TOPOLOGY_FILE")
            if env_override:
                topology_file = env_override
            else:
                # 默认路径：相对于项目根目录
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                candidates = [
                    os.path.join(project_root, "outputs", "spatial_data", "topology_data", "tianfu_topology.json"),
                    os.path.join(project_root, "outputs", "tianfu_topology.json"),
                    os.path.join(project_root, "scripts", "data_processing", "topology_map_based.json"),
                    os.path.join(project_root, "scripts", "data_processing", "topology_clustering_based.json"),
                ]
                topology_file = next((path for path in candidates if os.path.exists(path)), candidates[0])

        self.topology_file = topology_file
        self.topology: Optional[Dict[str, Any]] = None
        self._adjacency_map: Optional[Dict[str, Set[str]]] = None
        self._node_types: Optional[Dict[str, List[str]]] = None

    def load(self) -> Dict[str, Any]:
        """加载拓扑图数据"""
        if self.topology is not None:
            return self.topology

        try:
            with open(self.topology_file, 'r', encoding='utf-8') as f:
                graph = json.load(f)

            # 处理数据结构
            self.topology = {
                'nodes': graph.get('nodes', {}),
                'edges': graph.get('edges', [])
            }

            # 构建邻接表
            self._build_adjacency_map()

            # 构建节点类型索引
            self._build_node_type_index()

            return self.topology

        except FileNotFoundError:
            raise FileNotFoundError(
                f"拓扑图文件不存在: {self.topology_file}\n"
                f"请先运行 scripts/data_processing/build_topology_from_clustering.py 生成拓扑图"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"拓扑图文件格式错误: {e}")

    def _build_adjacency_map(self) -> None:
        """构建邻接表（无向图）"""
        assert self.topology is not None
        self._adjacency_map = defaultdict(set)

        for edge in self.topology['edges']:
            from_node = edge['from']
            to_node = edge['to']
            # 无向边
            self._adjacency_map[from_node].add(to_node)
            self._adjacency_map[to_node].add(from_node)

    def _build_node_type_index(self) -> None:
        """构建节点类型索引"""
        assert self.topology is not None
        self._node_types = {
            'stand': [],
            'runway': [],
            'taxiway': []
        }

        for node_id, node in self.topology['nodes'].items():
            node_type = node.get('type')
            if node_type in self._node_types:
                self._node_types[node_type].append(node_id)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点信息"""
        topology = self.load()
        return cast(Optional[Dict[str, Any]], topology['nodes'].get(node_id))

    def get_adjacent_nodes(self, node_id: str) -> Set[str]:
        """获取邻接节点"""
        if self._adjacency_map is None:
            self.load()
        assert self._adjacency_map is not None
        return self._adjacency_map.get(node_id, set())

    def get_nodes_by_type(self, node_type: str) -> List[str]:
        """获取指定类型的所有节点ID"""
        if self._node_types is None:
            self.load()
        assert self._node_types is not None
        return self._node_types.get(node_type, [])

    def find_nearest_node(
        self,
        position_str: str,
        node_type: Optional[str] = None
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        根据位置字符串查找最近的节点

        Args:
            position_str: 位置描述（可能是机位号、滑行道名等）
            node_type: 节点类型过滤（stand/runway/taxiway）

        Returns:
            (node_id, node_info) 或 None
        """
        topology = self.load()

        # 直接匹配节点ID
        if position_str in topology['nodes']:
            node = topology['nodes'][position_str]
            if node_type is None or node.get('type') == node_type:
                return (position_str, node)

        # 中英文映射
        zh_to_en_type = {
            '滑行道': 'taxiway',
            '跑道': 'runway',
            '机位': 'stand',
            '停机位': 'stand'
        }

        # 提取中文前缀和数字
        import re
        for zh_prefix, en_prefix in zh_to_en_type.items():
            if position_str.startswith(zh_prefix):
                # 提取数字部分
                number_match = re.search(r'\d+', position_str)
                if number_match:
                    number = number_match.group()

                    # 构造可能的节点ID
                    candidate_ids = [
                        f"{en_prefix}_{number}",
                        f"corrected_{en_prefix}_{number}"  # 处理 corrected_stand_X 格式
                    ]

                    for candidate_id in candidate_ids:
                        if candidate_id in topology['nodes']:
                            node = topology['nodes'][candidate_id]
                            if node_type is None or node.get('type') == en_prefix:
                                return (candidate_id, node)

        # 模糊匹配（去除前缀）
        position_str_lower = position_str.lower()
        for node_id, node in topology['nodes'].items():
            if node_type and node.get('type') != node_type:
                continue

            # 检查ID是否包含位置字符串
            if position_str_lower in node_id.lower():
                return (node_id, node)

        return None

    def get_stand_info(self, stand_id: str) -> Optional[Dict[str, Any]]:
        """获取机位详细信息"""
        node = self.get_node(stand_id)
        if node is None or node.get('type') != 'stand':
            return None

        # 获取相邻滑行道
        adjacent_nodes = self.get_adjacent_nodes(stand_id)
        adjacent_taxiways = []
        for n in adjacent_nodes:
            node_info = self.get_node(n)
            if node_info and node_info.get('type') == 'taxiway':
                adjacent_taxiways.append(n)

        # 查找最近的跑道
        nearest_runway = self._find_nearest_runway(stand_id)

        return {
            'id': stand_id,
            'type': 'stand',
            'lat': node['lat'],
            'lon': node['lon'],
            'adjacent_taxiways': adjacent_taxiways,
            'nearest_runway': nearest_runway,
            'observations': node.get('observations', 0),
            'avg_dwell_time': node.get('avg_dwell_time', 0)
        }

    def _find_nearest_runway(self, node_id: str) -> Optional[str]:
        """BFS查找最近的跑道节点"""
        if self._adjacency_map is None:
            self.load()
        assert self._adjacency_map is not None

        visited = {node_id}
        queue = [node_id]

        while queue:
            current = queue.pop(0)
            current_node = self.get_node(current)

            if current_node and current_node.get('type') == 'runway':
                return current

            for neighbor in self._adjacency_map.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return None

    def bfs_spread(self, start_node: str, max_hops: int) -> Set[str]:
        """
        BFS扩散算法 - 从起始节点扩散指定跳数

        Args:
            start_node: 起始节点ID
            max_hops: 最大扩散跳数

        Returns:
            受影响的所有节点ID集合
        """
        if self._adjacency_map is None:
            self.load()
        assert self._adjacency_map is not None
        adjacency_map = self._adjacency_map

        visited = {start_node}
        queue = [(start_node, 0)]

        while queue:
            node, hops = queue.pop(0)
            if hops >= max_hops:
                continue

            for neighbor in adjacency_map.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, hops + 1))

        return visited

    def bfs_spread_levels(self, start_node: str, max_hops: int) -> List[Set[str]]:
        """
        BFS扩散分层结果 - 返回每一跳的节点集合（包含起点在第0层）
        """
        if self._adjacency_map is None:
            self.load()
        assert self._adjacency_map is not None
        adjacency_map = self._adjacency_map

        visited = {start_node}
        layers: List[Set[str]] = [set([start_node])]
        queue = [(start_node, 0)]

        while queue:
            node, hops = queue.pop(0)
            if hops >= max_hops:
                continue
            for neighbor in adjacency_map.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_hops = hops + 1
                    while len(layers) <= next_hops:
                        layers.append(set())
                    layers[next_hops].add(neighbor)
                    queue.append((neighbor, next_hops))

        return layers

    def get_statistics(self) -> Dict[str, Any]:
        """获取拓扑图统计信息"""
        topology = self.load()
        assert self._node_types is not None

        return {
            'total_nodes': len(topology['nodes']),
            'total_edges': len(topology['edges']),
            'stands': len(self._node_types['stand']),
            'runways': len(self._node_types['runway']),
            'taxiways': len(self._node_types['taxiway'])
        }


# 全局单例
_topology_loader = None


def get_topology_loader() -> TopologyLoader:
    """获取全局拓扑加载器实例"""
    global _topology_loader
    if _topology_loader is None:
        _topology_loader = TopologyLoader()
        _topology_loader.load()
    return _topology_loader
