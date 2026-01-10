"""
基于轨迹聚类结果构建拓扑图（正确方法）
"""
import json
import math
import numpy as np
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from sklearn.cluster import DBSCAN


class ClusteringBasedTopologyBuilder:
    """基于聚类结果的拓扑图构建器"""

    def __init__(self):
        self.graph = {
            'nodes': {},
            'edges': []
        }
        self.node_index = {}  # 用于快速查找节点

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点间距离（米）"""
        R = 6371000
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def add_node(self, node_id: str, node_type: str, lat: float, lon: float, **kwargs):
        """添加节点"""
        self.graph['nodes'][node_id] = {
            'id': node_id,
            'type': node_type,
            'lat': lat,
            'lon': lon,
            **kwargs
        }
        self.node_index[node_id] = (lat, lon)

    def add_edge(self, from_id: str, to_id: str, **kwargs):
        """添加边"""
        if from_id in self.node_index and to_id in self.node_index:
            from_lat, from_lon = self.node_index[from_id]
            to_lat, to_lon = self.node_index[to_id]
            distance = self.calculate_distance(from_lat, from_lon, to_lat, to_lon)

            self.graph['edges'].append({
                'from': from_id,
                'to': to_id,
                'distance': distance,
                **kwargs
            })

    def find_nearest_node(self, lat: float, lon: float, node_type: str = None) -> Tuple[str, float]:
        """找到最近的节点"""
        min_dist = float('inf')
        nearest_id = None

        for node_id, node in self.graph['nodes'].items():
            if node_type and node['type'] != node_type:
                continue

            dist = self.calculate_distance(lat, lon, node['lat'], node['lon'])
            if dist < min_dist:
                min_dist = dist
                nearest_id = node_id

        return nearest_id, min_dist

    def build_from_clustering_results(
        self,
        clustering_results: Dict[str, Any],
        trajectory_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        基于聚类结果构建拓扑图

        Args:
            clustering_results: trajectory_clustering.py 的输出
            trajectory_data: 原始航迹数据（用于构建边）
        """
        print("\n" + "=" * 60)
        print("基于聚类结果构建拓扑图")
        print("=" * 60)

        stands = clustering_results['stands']
        taxiways = clustering_results['taxiways']
        runways = clustering_results['runways']

        # Step 1: 添加所有节点
        print("\n[1/4] 添加节点...")

        # 添加机位节点
        for stand in stands:
            self.add_node(
                node_id=stand['id'],
                node_type='stand',
                lat=stand['lat'],
                lon=stand['lon'],
                observations=stand['observations'],
                avg_dwell_time=stand['avg_dwell_time']
            )
        print(f"  添加 {len(stands)} 个机位节点")

        # 添加跑道节点
        for runway in runways:
            self.add_node(
                node_id=runway['id'],
                node_type='runway',
                lat=runway['lat'],
                lon=runway['lon'],
                observations=runway['observations'],
                avg_speed=runway['avg_speed'],
                avg_heading=runway['avg_heading']
            )
        print(f"  添加 {len(runways)} 个跑道节点")

        # 添加滑行道节点（作为交叉点）
        # 【修复】过滤异常节点：计算中心点，移除距离太远的节点
        if stands and taxiways:
            # 计算机场中心（基于机位）
            center_lat = sum(s['lat'] for s in stands) / len(stands)
            center_lon = sum(s['lon'] for s in stands) / len(stands)

            # 过滤滑行道：只保留距离机场中心10公里内的
            filtered_taxiways = []
            for taxiway in taxiways:
                dist = self.calculate_distance(
                    center_lat, center_lon,
                    taxiway['lat'], taxiway['lon']
                )
                if dist <= 10000:  # 10公里内
                    filtered_taxiways.append(taxiway)

            print(f"  过滤异常节点: {len(taxiways)} → {len(filtered_taxiways)}")
            taxiways = filtered_taxiways

        for taxiway in taxiways:
            self.add_node(
                node_id=taxiway['id'],
                node_type='taxiway',
                lat=taxiway['lat'],
                lon=taxiway['lon'],
                point_count=taxiway['point_count'],
                avg_speed=taxiway['avg_speed']
            )
        print(f"  添加 {len(taxiways)} 个滑行道节点")

        # Step 2: 基于实际滑行轨迹构建边
        print("\n[2/4] 基于滑行轨迹构建边...")
        self._build_edges_from_trajectories(trajectory_data)

        # Step 3: 优化图结构
        print("\n[3/4] 优化图结构...")
        self._remove_duplicate_edges()
        self._merge_close_nodes()

        # Step 4: 计算统计信息
        print("\n[4/4] 计算统计信息...")
        stats = self._calculate_stats()

        return {
            'graph': self.graph,
            'statistics': stats
        }

    def _build_edges_from_trajectories(self, trajectory_data: List[Dict[str, Any]]):
        """基于实际轨迹构建边"""
        # 按航班分组轨迹
        from collections import defaultdict
        trajectories = defaultdict(list)

        for point in trajectory_data:
            alt = point.get('ALT') or 0
            speed = point.get('groundspeed') or 0
            if (point.get('targettype') == 'Aircraft' and
                alt < 600 and 0.5 <= speed <= 50):
                callsign = point.get('CALLSIGN')
                if callsign:
                    trajectories[callsign].append(point)

        # 排序
        for callsign in trajectories:
            trajectories[callsign].sort(key=lambda x: x.get('TIME', ''))

        # 对每条轨迹，找到经过的节点序列
        edge_usage = defaultdict(int)

        for callsign, trajectory in trajectories.items():
            if len(trajectory) < 2:
                continue

            # 将轨迹点映射到最近的节点
            visited_nodes = []
            for point in trajectory:
                nearest_node, dist = self.find_nearest_node(
                    point['LAT'],
                    point['LON']
                )
                # 只考虑距离小于200米的节点
                if nearest_node and dist < 200:
                    if not visited_nodes or visited_nodes[-1] != nearest_node:
                        visited_nodes.append(nearest_node)

            # 为连续节点添加边
            for i in range(len(visited_nodes) - 1):
                edge_key = tuple(sorted([visited_nodes[i], visited_nodes[i + 1]]))
                edge_usage[edge_key] += 1

        # 添加边
        for (node1, node2), count in edge_usage.items():
            self.add_edge(
                from_id=node1,
                to_id=node2,
                usage_count=count
            )

        print(f"  识别到 {len(edge_usage)} 条边连接")

    def _remove_duplicate_edges(self):
        """移除重复边"""
        unique_edges = {}
        for edge in self.graph['edges']:
            key = tuple(sorted([edge['from'], edge['to']]))
            if key not in unique_edges:
                unique_edges[key] = edge
            else:
                # 合并使用次数
                unique_edges[key]['usage_count'] = unique_edges[key].get('usage_count', 1) + edge.get('usage_count', 1)

        self.graph['edges'] = list(unique_edges.values())

    def _merge_close_nodes(self, distance_threshold=50):
        """合并距离很近的同类节点"""
        # 按类型分组节点
        nodes_by_type = defaultdict(list)
        for node_id, node in self.graph['nodes'].items():
            nodes_by_type[node['type']].append((node_id, node))

        # 对每种类型进行合并
        nodes_to_remove = set()
        node_mapping = {}  # 旧节点ID -> 新节点ID

        for node_type, nodes in nodes_by_type.items():
            if len(nodes) < 2:
                continue

            # 提取坐标
            coords = np.array([[n[1]['lat'], n[1]['lon']] for n in nodes])
            node_ids = [n[0] for n in nodes]

            # DBSCAN聚类（合并距离很近的节点）
            # 50米 ≈ 0.00045度
            clustering = DBSCAN(eps=distance_threshold / 111000, min_samples=1).fit(coords)
            labels = clustering.labels_

            # 合并聚类
            clusters = defaultdict(list)
            for i, label in enumerate(labels):
                clusters[label].append(i)

            for label, indices in clusters.items():
                if len(indices) <= 1:
                    continue

                # 保留第一个节点，删除其他节点
                keep_id = node_ids[indices[0]]
                for i in indices[1:]:
                    remove_id = node_ids[i]
                    nodes_to_remove.add(remove_id)
                    node_mapping[remove_id] = keep_id

        # 移除节点
        for node_id in nodes_to_remove:
            del self.graph['nodes'][node_id]

        # 更新边中的节点引用
        updated_edges = []
        for edge in self.graph['edges']:
            from_id = node_mapping.get(edge['from'], edge['from'])
            to_id = node_mapping.get(edge['to'], edge['to'])

            # 跳过自环
            if from_id != to_id:
                edge['from'] = from_id
                edge['to'] = to_id
                updated_edges.append(edge)

        self.graph['edges'] = updated_edges

        if nodes_to_remove:
            print(f"  合并了 {len(nodes_to_remove)} 个相近节点")

    def _calculate_stats(self) -> Dict[str, Any]:
        """计算统计信息"""
        nodes_by_type = defaultdict(int)
        for node in self.graph['nodes'].values():
            nodes_by_type[node['type']] += 1

        total_distance = sum(e['distance'] for e in self.graph['edges'])
        avg_distance = total_distance / len(self.graph['edges']) if self.graph['edges'] else 0

        # 节点连接度
        node_connections = defaultdict(int)
        for edge in self.graph['edges']:
            node_connections[edge['from']] += 1
            node_connections[edge['to']] += 1

        # 最繁忙的边
        busiest_edge = max(
            self.graph['edges'],
            key=lambda e: e.get('usage_count', 0)
        ) if self.graph['edges'] else None

        # 最繁忙的节点
        busiest_node = max(
            node_connections.items(),
            key=lambda x: x[1]
        ) if node_connections else None

        return {
            'total_nodes': len(self.graph['nodes']),
            'nodes_by_type': dict(nodes_by_type),
            'total_edges': len(self.graph['edges']),
            'total_distance': total_distance,
            'avg_edge_distance': avg_distance,
            'busiest_edge': {
                'from': busiest_edge['from'],
                'to': busiest_edge['to'],
                'usage_count': busiest_edge.get('usage_count', 0),
                'distance': busiest_edge['distance']
            } if busiest_edge else None,
            'busiest_node': {
                'node_id': busiest_node[0],
                'node_type': self.graph['nodes'][busiest_node[0]]['type'],
                'connections': busiest_node[1]
            } if busiest_node else None,
        }

    def save_graph(self, output_file: str):
        """保存拓扑图"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.graph, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 拓扑图已保存: {output_file}")


if __name__ == "__main__":
    from parse_trajectory import TrajectoryParser, filter_by_time_range

    project_root = Path(__file__).resolve().parents[2]

    # 读取聚类结果
    print("读取聚类结果...")
    clustering_path = project_root / "scripts" / "data_processing" / "trajectory_clustering_results.json"
    with open(clustering_path, 'r') as f:
        clustering_results = json.load(f)

    # 读取航迹数据（用于构建边）
    print("读取航迹数据...")
    parser = TrajectoryParser()
    traj_dir = project_root / "data" / "raw" / "航迹数据"
    traj_data = parser.parse_file(traj_dir / "2025-10-21_11h.log")

    filtered = filter_by_time_range(
        traj_data,
        "2025-10-21 11:00:00",
        "2025-10-21 12:00:00"
    )

    print(f"时段数据: {len(filtered)} 条")

    # 构建拓扑图
    builder = ClusteringBasedTopologyBuilder()
    result = builder.build_from_clustering_results(clustering_results, filtered)

    # 保存
    output_file = project_root / "scripts" / "data_processing" / "topology_clustering_based.json"
    builder.save_graph(str(output_file))

    # 打印统计
    print("\n" + "=" * 60)
    print("拓扑图统计（基于聚类）")
    print("=" * 60)
    stats = result['statistics']
    print(f"总节点数: {stats['total_nodes']}")
    print(f"  - 机位: {stats['nodes_by_type'].get('stand', 0)}")
    print(f"  - 跑道: {stats['nodes_by_type'].get('runway', 0)}")
    print(f"  - 滑行道: {stats['nodes_by_type'].get('taxiway', 0)}")
    print(f"\n总边数: {stats['total_edges']}")
    print(f"平均边长: {stats['avg_edge_distance']:.1f} 米")

    if stats['busiest_edge']:
        print(f"\n最繁忙连接:")
        e = stats['busiest_edge']
        print(f"  {e['from']} ↔ {e['to']}")
        print(f"  使用次数: {e['usage_count']}, 距离: {e['distance']:.1f}米")

    if stats['busiest_node']:
        print(f"\n最繁忙节点:")
        n = stats['busiest_node']
        print(f"  {n['node_id']} ({n['node_type']})")
        print(f"  连接数: {n['connections']}")
