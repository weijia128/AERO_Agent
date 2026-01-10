"""
修正版机位识别

基于您的建议，明确区分：
- 机位: ≤0.5 m/s (真正静止)
- 滑行道: 0.5-20 m/s (缓慢滑行)
"""
import numpy as np
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any, Tuple
from sklearn.cluster import DBSCAN


class CorrectedStandDetector:
    """修正版机位检测器（明确区分机位和滑行道）"""

    def __init__(self):
        self.trajectories = {}

    def detect_stands(self, surface_trajectories: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        检测机位

        关键修正：
        - 机位: 速度 ≤ 0.5 m/s + 长时间停留
        - 滑行道: 速度 0.5-20 m/s
        - 跑道: 速度 ≥ 30 m/s
        """
        self.trajectories = surface_trajectories

        print("\n" + "=" * 60)
        print("修正版机位识别（区分机位 vs 滑行道）")
        print("=" * 60)
        print("\n速度阈值:")
        print("  机位: ≤ 0.5 m/s (真正静止)")
        print("  滑行道: 0.5-20 m/s (滑行)")
        print("  跑道: ≥ 30 m/s (高速)")
        print("=" * 60)

        stand_candidates = []

        for callsign, trajectory in self.trajectories.items():
            # 找到真正静止的段（≤0.5 m/s）
            stationary_segments = self._extract_stationary_segments(trajectory)

            for segment in stationary_segments:
                stand_candidates.append({
                    'callsign': callsign,
                    'lat': segment['lat'],
                    'lon': segment['lon'],
                    'duration': segment['duration'],
                    'point_count': segment['point_count'],
                    'avg_speed': segment['avg_speed'],
                    'max_speed': segment['max_speed']
                })

        print(f"\n静止候选点: {len(stand_candidates)} 个")

        if not stand_candidates:
            print("⚠️ 警告: 没有检测到静止数据")
            print("   可能原因: GPS精度限制或速度阈值过高")
            print("   建议: 降低速度阈值或使用位置稳定性分析")

            # 备选方案：使用位置稳定性分析
            return self._detect_stands_by_stability()

        # 对静止点进行聚类
        stands = self._cluster_stands(stand_candidates)

        print(f"\n识别机位: {len(stands)} 个")
        return stands

    def _extract_stationary_segments(self, trajectory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取静止段（≤0.5 m/s）"""
        segments = []
        current_segment = []

        # 关键修正: 速度阈值 0.5 m/s（而不是2.0 m/s）
        for point in trajectory:
            speed = point.get('groundspeed', 0)
            if speed <= 0.5:  # 真正静止
                current_segment.append(point)
            else:
                if len(current_segment) >= 5:  # 至少5个连续静止点
                    segments.append(self._analyze_segment(current_segment))
                current_segment = []

        # 处理最后一段
        if len(current_segment) >= 5:
            segments.append(self._analyze_segment(current_segment))

        return segments

    def _analyze_segment(self, segment: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析停留段"""
        if len(segment) < 2:
            return {'lat': 0, 'lon': 0, 'duration': 0, 'point_count': 0}

        try:
            start_time = datetime.fromisoformat(segment[0]['TIME'])
            end_time = datetime.fromisoformat(segment[-1]['TIME'])
            duration = (end_time - start_time).total_seconds()
        except:
            duration = 0

        lat = sum(p['LAT'] for p in segment) / len(segment)
        lon = sum(p['LON'] for p in segment) / len(segment)
        speeds = [p.get('groundspeed', 0) for p in segment]

        return {
            'lat': lat,
            'lon': lon,
            'duration': duration,
            'point_count': len(segment),
            'avg_speed': sum(speeds) / len(speeds),
            'max_speed': max(speeds),
            'start_time': segment[0]['TIME'],
            'end_time': segment[-1]['TIME']
        }

    def _cluster_stands(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """聚类静止点为机位"""
        if not candidates:
            return []

        # 提取坐标
        coords = np.array([[c['lat'], c['lon']] for c in candidates])

        # DBSCAN聚类（10米半径）
        clustering = DBSCAN(eps=0.0001, min_samples=1).fit(coords)
        labels = clustering.labels_

        # 统计聚类
        clusters = defaultdict(list)
        for i, label in enumerate(labels):
            clusters[label].append(candidates[i])

        # 计算每个聚类的中心
        stands = []
        for label, points in clusters.items():
            avg_lat = sum(p['lat'] for p in points) / len(points)
            avg_lon = sum(p['lon'] for p in points) / len(points)
            total_duration = sum(p.get('duration', 0) for p in points)
            avg_duration = total_duration / len(points)

            stands.append({
                'id': f'corrected_stand_{label}',
                'type': 'stand',
                'lat': avg_lat,
                'lon': avg_lon,
                'observations': len(points),
                'total_dwell_time': total_duration,
                'avg_dwell_time': avg_duration,
                'detection_method': 'stationary_analysis'
            })

        return stands

    def _detect_stands_by_stability(self) -> List[Dict[str, Any]]:
        """
        备选方案: 基于位置稳定性分析
        即使速度>0.5 m/s，如果位置基本不变也可能是机位
        """
        print("\n[备选方案] 使用位置稳定性分析...")

        stability_candidates = []

        for callsign, trajectory in self.trajectories.items():
            # 分析轨迹的稳定性
            for i in range(len(trajectory) - 10):
                window = trajectory[i:i+10]
                speeds = [p.get('groundspeed', 0) for p in window]

                # 如果平均速度较低
                avg_speed = sum(speeds) / len(speeds)
                if avg_speed < 2.0:  # 允许稍高的速度

                    # 计算位置变化
                    lats = [p['LAT'] for p in window]
                    lons = [p['LON'] for p in window]

                    lat_std = np.std(lats)
                    lon_std = np.std(lons)

                    # 如果位置变化很小（标准差 < 0.00005度 ≈ 5米）
                    if lat_std < 0.00005 and lon_std < 0.00005:
                        # 这可能是机位
                        avg_lat = sum(lats) / len(lats)
                        avg_lon = sum(lons) / len(lons)

                        # 计算时间跨度
                        try:
                            start_time = datetime.fromisoformat(window[0]['TIME'])
                            end_time = datetime.fromisoformat(window[-1]['TIME'])
                            duration = (end_time - start_time).total_seconds()
                        except:
                            duration = 0

                        if duration >= 30:  # 至少30秒
                            stability_candidates.append({
                                'callsign': callsign,
                                'lat': avg_lat,
                                'lon': avg_lon,
                                'duration': duration,
                                'avg_speed': avg_speed,
                                'position_stability': 1.0 / (1.0 + lat_std + lon_std)
                            })

        print(f"  稳定性候选: {len(stability_candidates)} 个")

        if stability_candidates:
            return self._cluster_stands(stability_candidates)

        return []

    @staticmethod
    def get_speed_statistics(surface_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取场面速度统计（用于验证阈值选择）"""
        speeds = [p.get('groundspeed', 0) for p in surface_points if p.get('groundspeed') is not None]
        speeds.sort()

        if not speeds:
            return {}

        stats = {
            'min_speed': min(speeds),
            'max_speed': max(speeds),
            'median_speed': speeds[len(speeds) // 2],
            'total_points': len(speeds),
            'speed_ranges': {
                'stationary_0_0.5': sum(1 for s in speeds if 0 <= s < 0.5),
                'slow_0.5_2': sum(1 for s in speeds if 0.5 <= s < 2.0),
                'normal_2_10': sum(1 for s in speeds if 2.0 <= s < 10.0),
                'fast_10_20': sum(1 for s in speeds if 10.0 <= s < 20.0),
                'very_fast_20_plus': sum(1 for s in speeds if s >= 20.0)
            }
        }

        return stats


if __name__ == "__main__":
    print("修正版机位识别模块")
    print("\n关键改进:")
    print("1. 机位识别: 速度阈值 0.5 m/s（而不是2.0 m/s）")
    print("2. 滑行道识别: 速度范围 0.5-20 m/s")
    print("3. 位置稳定性分析作为备选方案")
    print("\n使用方法:")
    print("detector = CorrectedStandDetector()")
    print("stands = detector.detect_stands(trajectories)")
