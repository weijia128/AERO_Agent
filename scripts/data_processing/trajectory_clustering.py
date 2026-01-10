"""
基于轨迹聚类的拓扑提取（修正版 - 基于用户反馈）

关键修正：
- 机位：基于位置稳定性分析（而不是速度阈值）
- 滑行道：0.5-20 m/s（明确区分）
- 跑道：≥30 m/s（基于速度模式）

修正说明：
1. 机位识别不再使用速度阈值（GPS无真正0 m/s）
2. 使用位置稳定性分析识别机位
3. 滑行道明确使用0.5-20 m/s范围
"""
import json
import numpy as np
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from sklearn.cluster import DBSCAN
from parse_trajectory import TrajectoryParser, filter_by_time_range
from corrected_stand_detection import CorrectedStandDetector


class TrajectoryClusteringAnalyzer:
    """基于轨迹聚类的分析器"""

    def __init__(self):
        self.surface_points = []
        self.trajectories_by_flight = {}

    def extract_surface_trajectories(self, trajectory_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """提取场面轨迹"""
        print("\n提取场面轨迹...")

        # 筛选场面数据
        surface = []
        for record in trajectory_data:
            alt = record.get('ALT') or 0
            speed = record.get('groundspeed') or 0
            if (record.get('targettype') == 'Aircraft' and
                alt < 600 and
                0.5 <= speed <= 50):
                surface.append(record)

        print(f"场面轨迹点: {len(surface)} 条")

        # 按航班分组
        by_flight = defaultdict(list)
        for point in surface:
            callsign = point.get('CALLSIGN')
            if callsign:
                by_flight[callsign].append(point)

        # 排序
        for callsign in by_flight:
            by_flight[callsign].sort(key=lambda x: x.get('TIME', ''))

        print(f"唯一航班数: {len(by_flight)}")

        self.surface_points = surface
        self.trajectories_by_flight = dict(by_flight)

        return {
            'surface_points': surface,
            'trajectories': dict(by_flight)
        }

    def cluster_by_dwelling_time(self, speed_threshold=2.0, time_threshold=30) -> List[Dict[str, Any]]:
        """
        方法1: 基于位置稳定性识别机位（修正版）

        关键修正：
        - 不再使用速度阈值（GPS无真正0 m/s数据）
        - 使用位置稳定性分析识别机位
        - 滑行道使用明确的0.5-20 m/s范围
        """
        print(f"\n识别机位（基于位置稳定性）...")

        # 使用修正版机位检测器
        detector = CorrectedStandDetector()

        # 检测机位
        stands = detector.detect_stands(self.trajectories_by_flight)

        if stands:
            print(f"识别机位: {len(stands)} 个")
            print("方法: 位置稳定性分析")
            return stands
        else:
            print("⚠️ 未识别到机位（数据中无足够静止点）")
            return []

    def cluster_by_trajectory_density(self, eps=0.0002, min_samples=10) -> List[Dict[str, Any]]:
        """
        方法2: 基于轨迹密度识别滑行道（修正版）

        关键修正：
        - 明确使用0.5-20 m/s范围
        - 与机位（≤0.5 m/s）明确区分
        - 排除高速点（≥20 m/s，可能是跑道）
        """
        print(f"\n识别滑行道（轨迹密集区域）...")

        if not self.surface_points:
            return []

        # 严格筛选：滑行道速度范围 0.5-20 m/s
        # 与机位（≤0.5 m/s）和跑道（≥20 m/s）明确区分
        taxiing_points = [
            p for p in self.surface_points
            if 0.5 <= (p.get('groundspeed') or 0) < 20  # 滑行速度：0.5-20 m/s
        ]

        print(f"  滑行速度点数: {len(taxiing_points)} / {len(self.surface_points)}")
        print(f"  速度范围: 0.5 - 20 m/s（与机位≤0.5 m/s明确区分）")

        if not taxiing_points:
            return []

        # 提取所有坐标
        coords = np.array([[p['LAT'], p['LON']] for p in taxiing_points])

        # DBSCAN聚类
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(coords)
        labels = clustering.labels_

        # 统计聚类
        clusters = defaultdict(list)
        for i, label in enumerate(labels):
            if label != -1:  # 忽略噪声
                clusters[label].append(taxiing_points[i])

        # 分析每个聚类
        taxiways = []
        for label, points in clusters.items():
            avg_lat = sum(p['LAT'] for p in points) / len(points)
            avg_lon = sum(p['LON'] for p in points) / len(points)
            avg_speed = sum(p.get('groundspeed', 0) for p in points) / len(points)

            taxiways.append({
                'id': f'taxiway_{label}',
                'type': 'taxiway',
                'lat': avg_lat,
                'lon': avg_lon,
                'point_count': len(points),
                'avg_speed': avg_speed
            })

        print(f"识别滑行道密集区: {len(taxiways)} 个")
        return taxiways

    def identify_runways_by_speed_pattern(self, speed_threshold=30) -> List[Dict[str, Any]]:
        """
        方法3: 基于速度模式识别跑道

        逻辑：飞机在跑道上速度高（起飞加速或落地减速）
        """
        print(f"\n识别跑道（高速区域）...")

        runway_candidates = []

        for callsign, trajectory in self.trajectories_by_flight.items():
            # 找高速段
            for i, point in enumerate(trajectory):
                speed = point.get('groundspeed', 0)
                if speed >= speed_threshold:  # 高速点
                    runway_candidates.append({
                        'callsign': callsign,
                        'lat': point['LAT'],
                        'lon': point['LON'],
                        'speed': speed,
                        'heading': point.get('heading', 0)
                    })

        print(f"高速候选点: {len(runway_candidates)} 个")

        # 聚类高速点
        if runway_candidates:
            coords = np.array([[p['lat'], p['lon']] for p in runway_candidates])
            clustering = DBSCAN(eps=0.001, min_samples=5).fit(coords)

            labels = clustering.labels_

            # 统计聚类
            clusters = defaultdict(list)
            for i, label in enumerate(labels):
                if label != -1:
                    clusters[label].append(runway_candidates[i])

            # 分析每个聚类
            runways = []
            for label, points in clusters.items():
                avg_lat = sum(p['lat'] for p in points) / len(points)
                avg_lon = sum(p['lon'] for p in points) / len(points)
                avg_speed = sum(p['speed'] for p in points) / len(points)
                avg_heading = sum(p['heading'] for p in points) / len(points)

                runways.append({
                    'id': f'runway_{label}',
                    'type': 'runway',
                    'lat': avg_lat,
                    'lon': avg_lon,
                    'observations': len(points),
                    'avg_speed': avg_speed,
                    'avg_heading': avg_heading
                })

            print(f"识别跑道: {len(runways)} 个")
            return runways

        return []

    def analyze(self, trajectory_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """完整分析（修正版）"""
        print("=" * 60)
        print("轨迹聚类分析（修正版 - 基于用户反馈）")
        print("=" * 60)
        print("\n修正说明:")
        print("  机位: 基于位置稳定性分析（不使用速度阈值）")
        print("  滑行道: 速度范围 0.5-20 m/s")
        print("  跑道: 速度范围 ≥30 m/s")
        print("=" * 60)

        # 提取场面轨迹
        self.extract_surface_trajectories(trajectory_data)

        # 识别机位（基于位置稳定性）
        stands = self.cluster_by_dwelling_time()

        # 识别滑行道（0.5-20 m/s）
        taxiways = self.cluster_by_trajectory_density(eps=0.0002, min_samples=10)

        # 识别跑道（≥30 m/s）
        runways = self.identify_runways_by_speed_pattern(speed_threshold=30)

        return {
            'stands': stands,
            'taxiways': taxiways,
            'runways': runways,
            'summary': {
                'stands': len(stands),
                'taxiways': len(taxiways),
                'runways': len(runways)
            }
        }

    def save_results(self, results: Dict[str, Any], output_file: str):
        """保存结果"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 结果已保存: {output_file}")


if __name__ == "__main__":
    # 读取数据
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

    print(f"时段数据: {len(filtered)} 条")

    # 轨迹聚类分析
    analyzer = TrajectoryClusteringAnalyzer()
    results = analyzer.analyze(filtered)

    # 保存结果
    analyzer.save_results(
        results,
        str(project_root / "scripts" / "data_processing" / "trajectory_clustering_results.json")
    )

    # 打印结果
    print("\n" + "=" * 60)
    print("聚类结果对比（修正版）")
    print("=" * 60)
    print(f"\n基于位置稳定性识别:")
    print(f"  机位: {results['summary']['stands']} 个（方法：位置稳定性分析）")

    print(f"\n基于轨迹密度识别:")
    print(f"  滑行道区域: {results['summary']['taxiways']} 个（速度范围：0.5-20 m/s）")

    print(f"\n基于速度模式识别:")
    print(f"  跑道: {results['summary']['runways']} 个（速度范围：≥30 m/s）")

    # 显示机位样例
    if results['stands']:
        print(f"\n机位样例（前5个）:")
        for stand in results['stands'][:5]:
            print(f"  {stand['id']}: ({stand['lat']:.6f}, {stand['lon']:.6f})")
            print(f"    观测次数: {stand['observations']}, 平均停留: {stand['avg_dwell_time']:.0f}秒")

    # 显示跑道样例
    if results['runways']:
        print(f"\n跑道样例:")
        for runway in results['runways']:
            print(f"  {runway['id']}: ({runway['lat']:.6f}, {runway['lon']:.6f})")
            print(f"    平均速度: {runway['avg_speed']:.1f} m/s, 航向: {runway['avg_heading']:.0f}°")
