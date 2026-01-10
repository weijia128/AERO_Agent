"""
滑行路径提取工具

从航迹数据中提取场面滑行路径，识别：
- 机位位置
- 滑行道路径
- 跑道入口
- 关键转折点
"""
import json
import math
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from pathlib import Path

try:
    from data_processing.parse_trajectory import TrajectoryParser
except ModuleNotFoundError:
    from parse_trajectory import TrajectoryParser


class TaxiPathExtractor:
    """滑行路径提取器"""

    def __init__(self, surface_alt_threshold=600, min_speed=0.5, max_speed=50):
        """
        Args:
            surface_alt_threshold: 场面高度阈值（米）
            min_speed: 最小滑行速度（m/s）
            max_speed: 最大滑行速度（m/s）
        """
        self.surface_alt_threshold = surface_alt_threshold
        self.min_speed = min_speed
        self.max_speed = max_speed

    def is_surface_movement(self, record: Dict[str, Any]) -> bool:
        """判断是否为场面滑行数据"""
        alt = record.get('ALT') or 0
        speed = record.get('groundspeed') or 0
        target_type = record.get('targettype')

        return (
            target_type == 'Aircraft' and
            alt < self.surface_alt_threshold and
            self.min_speed <= speed <= self.max_speed
        )

    def extract_surface_trajectories(
        self,
        trajectory_data: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        提取所有场面滑行轨迹

        Returns:
            {callsign: [trajectory_points...]}
        """
        # 筛选场面数据
        surface_data = [r for r in trajectory_data if self.is_surface_movement(r)]

        print(f"场面滑行记录数: {len(surface_data)} / {len(trajectory_data)}")

        # 按呼号分组
        by_callsign = defaultdict(list)
        for record in surface_data:
            callsign = record.get('CALLSIGN')
            if callsign:
                by_callsign[callsign].append(record)

        # 按时间排序
        for callsign in by_callsign:
            by_callsign[callsign].sort(key=lambda x: x.get('TIME', ''))

        print(f"唯一航班数: {len(by_callsign)}")

        return dict(by_callsign)

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点间距离（米），使用Haversine公式"""
        R = 6371000  # 地球半径（米）

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def calculate_heading_change(self, h1: float, h2: float) -> float:
        """计算航向变化（度）"""
        diff = abs(h2 - h1)
        if diff > 180:
            diff = 360 - diff
        return diff

    def identify_turning_points(
        self,
        trajectory: List[Dict[str, Any]],
        heading_threshold: float = 30.0
    ) -> List[Dict[str, Any]]:
        """
        识别转折点（航向变化明显的点）

        Args:
            trajectory: 轨迹点列表
            heading_threshold: 航向变化阈值（度）
        """
        if len(trajectory) < 3:
            return []

        turning_points = []

        for i in range(1, len(trajectory) - 1):
            prev_heading = trajectory[i - 1].get('heading', 0)
            curr_heading = trajectory[i].get('heading', 0)
            next_heading = trajectory[i + 1].get('heading', 0)

            # 计算航向变化
            change1 = self.calculate_heading_change(prev_heading, curr_heading)
            change2 = self.calculate_heading_change(curr_heading, next_heading)

            if change1 > heading_threshold or change2 > heading_threshold:
                turning_points.append({
                    **trajectory[i],
                    'heading_change': max(change1, change2),
                    'point_type': 'turning_point'
                })

        return turning_points

    def extract_taxi_path(
        self,
        callsign: str,
        trajectory: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        提取单个航班的完整滑行路径

        Returns:
            {
                'callsign': str,
                'start_point': dict,  # 起点（机位或跑道）
                'end_point': dict,    # 终点（跑道或机位）
                'trajectory': list,   # 完整轨迹
                'turning_points': list,  # 转折点
                'path_length': float,    # 路径长度（米）
                'duration': float,       # 滑行时长（秒）
            }
        """
        if len(trajectory) < 2:
            return None

        # 起点和终点
        start = trajectory[0]
        end = trajectory[-1]

        # 计算路径总长度
        total_distance = 0
        for i in range(len(trajectory) - 1):
            lat1 = trajectory[i].get('LAT', 0)
            lon1 = trajectory[i].get('LON', 0)
            lat2 = trajectory[i + 1].get('LAT', 0)
            lon2 = trajectory[i + 1].get('LON', 0)
            total_distance += self.calculate_distance(lat1, lon1, lat2, lon2)

        # 计算滑行时长
        from datetime import datetime
        try:
            start_time = datetime.fromisoformat(start.get('TIME', ''))
            end_time = datetime.fromisoformat(end.get('TIME', ''))
            duration = (end_time - start_time).total_seconds()
        except:
            duration = 0

        # 识别转折点
        turning_points = self.identify_turning_points(trajectory)

        # 提取机位和跑道信息
        start_stand = (start.get('stand') or '').strip() or None
        start_runway = (start.get('runway') or '').strip() or None
        end_stand = (end.get('stand') or '').strip() or None
        end_runway = (end.get('runway') or '').strip() or None

        return {
            'callsign': callsign,
            'start_point': {
                'lat': start.get('LAT'),
                'lon': start.get('LON'),
                'stand': start_stand,
                'runway': start_runway,
                'time': start.get('TIME'),
            },
            'end_point': {
                'lat': end.get('LAT'),
                'lon': end.get('LON'),
                'stand': end_stand,
                'runway': end_runway,
                'time': end.get('TIME'),
            },
            'trajectory': trajectory,
            'turning_points': turning_points,
            'path_length': total_distance,
            'duration': duration,
            'num_points': len(trajectory),
        }

    def analyze_paths(
        self,
        trajectory_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析所有滑行路径

        Returns:
            {
                'paths': list,           # 所有滑行路径
                'stand_locations': dict, # 机位位置统计
                'runway_entrances': dict, # 跑道入口位置
                'turning_points': list,  # 所有转折点
            }
        """
        print("\n" + "=" * 60)
        print("滑行路径提取")
        print("=" * 60)

        # 提取场面轨迹
        print("\n[1/3] 提取场面轨迹...")
        surface_trajectories = self.extract_surface_trajectories(trajectory_data)

        # 提取滑行路径
        print("\n[2/3] 分析滑行路径...")
        paths = []
        for callsign, trajectory in surface_trajectories.items():
            path = self.extract_taxi_path(callsign, trajectory)
            if path:
                paths.append(path)

        print(f"提取到 {len(paths)} 条有效滑行路径")

        # 统计机位位置
        print("\n[3/3] 统计关键位置...")
        stand_locations = self._extract_stand_locations(paths)
        runway_entrances = self._extract_runway_entrances(paths)
        all_turning_points = []
        for path in paths:
            all_turning_points.extend(path['turning_points'])

        print(f"识别到 {len(stand_locations)} 个机位位置")
        print(f"识别到 {len(runway_entrances)} 个跑道入口")
        print(f"识别到 {len(all_turning_points)} 个转折点")

        return {
            'paths': paths,
            'stand_locations': stand_locations,
            'runway_entrances': runway_entrances,
            'turning_points': all_turning_points,
            'summary': {
                'total_paths': len(paths),
                'total_stands': len(stand_locations),
                'total_runways': len(runway_entrances),
                'total_turning_points': len(all_turning_points),
            }
        }

    def _extract_stand_locations(self, paths: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """提取机位位置（从起点/终点中有机位信息的点）"""
        stand_positions = defaultdict(list)

        for path in paths:
            # 检查起点
            start = path['start_point']
            if start['stand']:
                stand_positions[start['stand']].append({
                    'lat': start['lat'],
                    'lon': start['lon']
                })

            # 检查终点
            end = path['end_point']
            if end['stand']:
                stand_positions[end['stand']].append({
                    'lat': end['lat'],
                    'lon': end['lon']
                })

        # 计算每个机位的平均位置
        stand_locations = {}
        for stand, positions in stand_positions.items():
            avg_lat = sum(p['lat'] for p in positions) / len(positions)
            avg_lon = sum(p['lon'] for p in positions) / len(positions)
            stand_locations[stand] = {
                'lat': avg_lat,
                'lon': avg_lon,
                'sample_count': len(positions)
            }

        return stand_locations

    def _extract_runway_entrances(self, paths: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """提取跑道入口位置"""
        runway_positions = defaultdict(list)

        for path in paths:
            # 检查起点
            start = path['start_point']
            if start['runway']:
                runway_positions[start['runway']].append({
                    'lat': start['lat'],
                    'lon': start['lon']
                })

            # 检查终点
            end = path['end_point']
            if end['runway']:
                runway_positions[end['runway']].append({
                    'lat': end['lat'],
                    'lon': end['lon']
                })

        # 计算每个跑道的平均入口位置
        runway_entrances = {}
        for runway, positions in runway_positions.items():
            avg_lat = sum(p['lat'] for p in positions) / len(positions)
            avg_lon = sum(p['lon'] for p in positions) / len(positions)
            runway_entrances[runway] = {
                'lat': avg_lat,
                'lon': avg_lon,
                'sample_count': len(positions)
            }

        return runway_entrances

    def save_results(self, results: Dict[str, Any], output_file: str):
        """保存结果到文件"""
        # 简化数据（移除完整轨迹以减小文件大小）
        simplified = {
            'summary': results['summary'],
            'stand_locations': results['stand_locations'],
            'runway_entrances': results['runway_entrances'],
            'paths_summary': [
                {
                    'callsign': p['callsign'],
                    'start_point': p['start_point'],
                    'end_point': p['end_point'],
                    'path_length': p['path_length'],
                    'duration': p['duration'],
                    'num_points': p['num_points'],
                    'num_turning_points': len(p['turning_points']),
                }
                for p in results['paths']
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(simplified, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 结果已保存到: {output_file}")


if __name__ == "__main__":
    try:
        from data_processing.parse_trajectory import filter_by_time_range
    except ModuleNotFoundError:
        from parse_trajectory import filter_by_time_range

    # 解析航迹数据
    parser = TrajectoryParser()
    project_root = Path(__file__).resolve().parents[2]
    traj_dir = project_root / "data" / "raw" / "航迹数据"

    print("读取航迹数据...")
    traj_data = parser.parse_file(traj_dir / "2025-10-21_11h.log")

    # 筛选时段
    filtered = filter_by_time_range(
        traj_data,
        "2025-10-21 11:00:00",
        "2025-10-21 12:00:00"
    )

    print(f"时段数据: {len(filtered)} 条记录")

    # 提取滑行路径
    extractor = TaxiPathExtractor()
    results = extractor.analyze_paths(filtered)

    # 保存结果
    extractor.save_results(
        results,
        str(project_root / "scripts" / "data_processing" / "taxi_paths_11_12.json")
    )

    # 打印统计信息
    print("\n" + "=" * 60)
    print("统计摘要")
    print("=" * 60)
    print(f"滑行路径数: {results['summary']['total_paths']}")
    print(f"机位数: {results['summary']['total_stands']}")
    print(f"跑道数: {results['summary']['total_runways']}")
    print(f"转折点数: {results['summary']['total_turning_points']}")

    print(f"\n机位位置（前10个）:")
    for i, (stand, info) in enumerate(list(results['stand_locations'].items())[:10]):
        print(f"  {stand}: ({info['lat']:.5f}, {info['lon']:.5f}) - {info['sample_count']}次观测")

    print(f"\n跑道入口:")
    for runway, info in results['runway_entrances'].items():
        print(f"  {runway}: ({info['lat']:.5f}, {info['lon']:.5f}) - {info['sample_count']}次观测")
