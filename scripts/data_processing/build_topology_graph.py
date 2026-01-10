"""
机场拓扑图构建工具

基于滑行路径数据构建机场拓扑图：
- 节点：机位、跑道、滑行道交叉点
- 边：滑行道路径
- 权重：距离、使用频率
"""
import json
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Set
from collections import defaultdict
from pathlib import Path
from sklearn.cluster import DBSCAN


class TopologyGraphBuilder:
    """拓扑图构建器"""

    def __init__(self, clustering_eps=0.0005, min_samples=2):
        """
        Args:
            clustering_eps: DBSCAN聚类半径（度，约50米）
            min_samples: 最小样本数
        """
        self.clustering_eps = clustering_eps
        self.min_samples = min_samples
        self.graph = {
            'nodes': {},  # {node_id: node_info}
            'edges': [],  # [{from, to, weight, ...}]
        }

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

    def cluster_turning_points(self, turning_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对转折点进行聚类，识别滑行道交叉点

        Returns:
            聚类后的交叉点列表
        """
        if not turning_points:
            return []

        # 提取坐标
        coords = np.array([[p['LAT'], p['LON']] for p in turning_points])

        # DBSCAN聚类
        clustering = DBSCAN(eps=self.clustering_eps, min_samples=self.min_samples).fit(coords)
        labels = clustering.labels_

        # 统计每个聚类
        clusters = defaultdict(list)
        for i, label in enumerate(labels):
            if label != -1:  # 忽略噪声点
                clusters[label].append(turning_points[i])

        # 计算每个聚类的中心点
        intersections = []
        for label, points in clusters.items():
            avg_lat = sum(p['LAT'] for p in points) / len(points)
            avg_lon = sum(p['LON'] for p in points) / len(points)

            intersections.append({
                'id': f'intersection_{label}',
                'type': 'intersection',
                'lat': avg_lat,
                'lon': avg_lon,
                'point_count': len(points),
                'avg_heading_change': sum(p.get('heading_change', 0) for p in points) / len(points)
            })

        print(f"聚类结果: {len(turning_points)} 个转折点 → {len(intersections)} 个交叉点")

        return intersections

    def add_node(self, node_id: str, node_type: str, lat: float, lon: float, **kwargs):
        """添加节点"""
        self.graph['nodes'][node_id] = {
            'id': node_id,
            'type': node_type,
            'lat': lat,
            'lon': lon,
            **kwargs
        }

    def add_edge(self, from_id: str, to_id: str, distance: float, usage_count: int = 1, **kwargs):
        """添加边"""
        self.graph['edges'].append({
            'from': from_id,
            'to': to_id,
            'distance': distance,
            'usage_count': usage_count,
            **kwargs
        })

    def find_nearest_node(self, lat: float, lon: float, max_distance: float = 200) -> Tuple[str, float]:
        """
        找到最近的节点

        Returns:
            (node_id, distance)
        """
        min_dist = float('inf')
        nearest_id = None

        for node_id, node in self.graph['nodes'].items():
            dist = self.calculate_distance(lat, lon, node['lat'], node['lon'])
            if dist < min_dist and dist <= max_distance:
                min_dist = dist
                nearest_id = node_id

        return nearest_id, min_dist

    def build_graph(self, paths_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建拓扑图

        Args:
            paths_data: extract_taxi_paths.py 输出的数据

        Returns:
            拓扑图数据
        """
        print("\n" + "=" * 60)
        print("拓扑图构建")
        print("=" * 60)

        paths = paths_data['paths']
        stand_locations = paths_data['stand_locations']
        runway_entrances = paths_data['runway_entrances']
        turning_points = paths_data['turning_points']

        # Step 1: 添加机位节点
        print("\n[1/5] 添加机位节点...")
        for stand, info in stand_locations.items():
            self.add_node(
                node_id=f'stand_{stand}',
                node_type='stand',
                lat=info['lat'],
                lon=info['lon'],
                stand_name=stand,
                sample_count=info['sample_count']
            )
        print(f"添加 {len(stand_locations)} 个机位节点")

        # Step 2: 添加跑道节点
        print("\n[2/5] 添加跑道节点...")
        for runway, info in runway_entrances.items():
            self.add_node(
                node_id=f'runway_{runway}',
                node_type='runway',
                lat=info['lat'],
                lon=info['lon'],
                runway_name=runway,
                sample_count=info['sample_count']
            )
        print(f"添加 {len(runway_entrances)} 个跑道节点")

        # Step 3: 聚类转折点，识别交叉点
        print("\n[3/5] 识别滑行道交叉点...")
        intersections = self.cluster_turning_points(turning_points)
        for intersection in intersections:
            self.add_node(
                node_id=intersection['id'],
                node_type='intersection',
                lat=intersection['lat'],
                lon=intersection['lon'],
                point_count=intersection['point_count']
            )
        print(f"添加 {len(intersections)} 个交叉点节点")

        # Step 4: 根据滑行路径添加边
        print("\n[4/5] 构建滑行道连接...")
        edge_usage = defaultdict(int)  # 记录每条边的使用次数

        for path in paths:
            # 获取起点和终点
            start = path['start_point']
            end = path['end_point']

            # 起点节点
            if start['stand']:
                start_node_id = f"stand_{start['stand']}"
            elif start['runway']:
                start_node_id = f"runway_{start['runway']}"
            else:
                # 找最近的节点
                start_node_id, _ = self.find_nearest_node(start['lat'], start['lon'])

            # 终点节点
            if end['stand']:
                end_node_id = f"stand_{end['stand']}"
            elif end['runway']:
                end_node_id = f"runway_{end['runway']}"
            else:
                end_node_id, _ = self.find_nearest_node(end['lat'], end['lon'])

            if start_node_id and end_node_id:
                edge_key = tuple(sorted([start_node_id, end_node_id]))
                edge_usage[edge_key] += 1

        # 添加边到图中
        for (node1, node2), count in edge_usage.items():
            n1 = self.graph['nodes'][node1]
            n2 = self.graph['nodes'][node2]
            distance = self.calculate_distance(n1['lat'], n1['lon'], n2['lat'], n2['lon'])

            self.add_edge(
                from_id=node1,
                to_id=node2,
                distance=distance,
                usage_count=count
            )

        print(f"添加 {len(self.graph['edges'])} 条边")

        # Step 5: 计算统计信息
        print("\n[5/5] 计算统计信息...")
        stats = self._calculate_graph_stats()

        return {
            'graph': self.graph,
            'statistics': stats
        }

    def _calculate_graph_stats(self) -> Dict[str, Any]:
        """计算图统计信息"""
        nodes_by_type = defaultdict(int)
        for node in self.graph['nodes'].values():
            nodes_by_type[node['type']] += 1

        total_distance = sum(e['distance'] for e in self.graph['edges'])
        avg_distance = total_distance / len(self.graph['edges']) if self.graph['edges'] else 0

        # 最繁忙的边
        busiest_edge = max(self.graph['edges'], key=lambda e: e['usage_count']) if self.graph['edges'] else None

        # 连接度分析
        node_connections = defaultdict(int)
        for edge in self.graph['edges']:
            node_connections[edge['from']] += 1
            node_connections[edge['to']] += 1

        # 最繁忙的节点
        busiest_node = max(node_connections.items(), key=lambda x: x[1]) if node_connections else None

        return {
            'total_nodes': len(self.graph['nodes']),
            'nodes_by_type': dict(nodes_by_type),
            'total_edges': len(self.graph['edges']),
            'total_distance': total_distance,
            'avg_edge_distance': avg_distance,
            'busiest_edge': {
                'from': busiest_edge['from'],
                'to': busiest_edge['to'],
                'usage_count': busiest_edge['usage_count']
            } if busiest_edge else None,
            'busiest_node': {
                'node_id': busiest_node[0],
                'connections': busiest_node[1]
            } if busiest_node else None,
        }

    def export_to_existing_format(self) -> Dict[str, Any]:
        """
        导出为与现有代码兼容的格式

        格式与 tools/spatial/get_stand_location.py 中的 MOCK_TOPOLOGY 一致
        """
        stands = {}
        taxiways = {}
        runways = {}

        # 提取机位
        for node_id, node in self.graph['nodes'].items():
            if node['type'] == 'stand':
                stand_id = node['stand_name']
                # 找到连接的滑行道和跑道
                adjacent = []
                adjacent_taxiways = []
                nearest_runway = None

                for edge in self.graph['edges']:
                    if edge['from'] == node_id:
                        other_node = self.graph['nodes'][edge['to']]
                        adjacent.append(edge['to'])
                        if other_node['type'] == 'intersection':
                            adjacent_taxiways.append(edge['to'])
                        elif other_node['type'] == 'runway':
                            nearest_runway = other_node['runway_name']
                    elif edge['to'] == node_id:
                        other_node = self.graph['nodes'][edge['from']]
                        adjacent.append(edge['from'])
                        if other_node['type'] == 'intersection':
                            adjacent_taxiways.append(edge['from'])
                        elif other_node['type'] == 'runway':
                            nearest_runway = other_node['runway_name']

                stands[stand_id] = {
                    'id': stand_id,
                    'name': f'{stand_id}号机位',
                    'type': 'contact',  # 简化处理
                    'coordinates': [node['lon'], node['lat']],
                    'adjacent': adjacent,
                    'adjacent_taxiways': adjacent_taxiways,
                    'nearest_runway': nearest_runway,
                }

        # 提取跑道
        for node_id, node in self.graph['nodes'].items():
            if node['type'] == 'runway':
                runway_id = node['runway_name']
                runways[runway_id] = {
                    'id': runway_id,
                    'name': f'{runway_id}跑道',
                    'status': 'ACTIVE'
                }

        return {
            'stands': stands,
            'taxiways': taxiways,
            'runways': runways
        }

    def save_graph(self, output_file: str):
        """保存拓扑图"""
        data = {
            'graph': self.graph,
            'compatible_format': self.export_to_existing_format()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 拓扑图已保存到: {output_file}")


if __name__ == "__main__":
    # 读取滑行路径数据
    project_root = Path(__file__).resolve().parents[2]
    paths_file = project_root / "scripts" / "data_processing" / "taxi_paths_11_12.json"

    print("读取滑行路径数据...")
    # 需要重新运行提取，因为简化版没有完整数据
    # 这里我们重新生成
    from extract_taxi_paths import TaxiPathExtractor
    from parse_trajectory import TrajectoryParser, filter_by_time_range

    parser = TrajectoryParser()
    traj_dir = project_root / "data" / "raw" / "航迹数据"

    print("读取航迹数据...")
    traj_data = parser.parse_file(traj_dir / "2025-10-21_11h.log")

    filtered = filter_by_time_range(
        traj_data,
        "2025-10-21 11:00:00",
        "2025-10-21 12:00:00"
    )

    print(f"时段数据: {len(filtered)} 条记录")

    # 提取滑行路径
    extractor = TaxiPathExtractor()
    paths_data = extractor.analyze_paths(filtered)

    # 构建拓扑图
    builder = TopologyGraphBuilder(clustering_eps=0.0005, min_samples=3)
    result = builder.build_graph(paths_data)

    # 保存
    builder.save_graph(
        str(project_root / "scripts" / "data_processing" / "airport_topology_11_12.json")
    )

    # 打印统计
    print("\n" + "=" * 60)
    print("拓扑图统计")
    print("=" * 60)
    stats = result['statistics']
    print(f"总节点数: {stats['total_nodes']}")
    print(f"  - 机位: {stats['nodes_by_type'].get('stand', 0)}")
    print(f"  - 跑道: {stats['nodes_by_type'].get('runway', 0)}")
    print(f"  - 交叉点: {stats['nodes_by_type'].get('intersection', 0)}")
    print(f"总边数: {stats['total_edges']}")
    print(f"平均边长: {stats['avg_edge_distance']:.1f} 米")

    if stats['busiest_edge']:
        print(f"\n最繁忙滑行道:")
        print(f"  {stats['busiest_edge']['from']} ↔ {stats['busiest_edge']['to']}")
        print(f"  使用次数: {stats['busiest_edge']['usage_count']}")

    if stats['busiest_node']:
        print(f"\n最繁忙节点:")
        print(f"  {stats['busiest_node']['node_id']}")
        print(f"  连接数: {stats['busiest_node']['connections']}")
