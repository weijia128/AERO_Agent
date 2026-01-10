"""
增强版机位识别

基于多维度特征的机位检测：
1. 长时间停留（≥5分钟）
2. 短时间停留的聚类
3. 位置稳定性分析
"""
import numpy as np
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any, Tuple
from sklearn.cluster import DBSCAN


class EnhancedStandDetector:
    """增强版机位检测器"""

    def __init__(self):
        self.trajectories = {}
        self.stand_candidates = []

    def detect_stands_from_trajectories(self, surface_trajectories: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        从轨迹数据中检测机位

        Args:
            surface_trajectories: 按航班分组的轨迹数据

        Returns:
            检测到的机位列表
        """
        self.trajectories = surface_trajectories

        print("\n" + "=" * 60)
        print("增强版机位识别")
        print("=" * 60)

        # 方法1: 长时间停留检测
        long_dwell_stands = self._detect_long_dwell_stands()
        print(f"[方法1] 长时间停留检测: {len(long_dwell_stands)} 个机位")

        # 方法2: 短时间停留聚类
        short_dwell_stands = self._detect_short_dwell_stands()
        print(f"[方法2] 短时间停留聚类: {len(short_dwell_stands)} 个机位")

        # 方法3: 位置稳定性分析
        stable_position_stands = self._detect_stable_positions()
        print(f"[方法3] 位置稳定性分析: {len(stable_position_stands)} 个机位")

        # 合并结果
        all_stands = long_dwell_stands + short_dwell_stands + stable_position_stands

        # 去重（相同位置的机位合并）
        merged_stands = self._merge_duplicate_stands(all_stands)
        print(f"\n合并后机位数: {len(merged_stands)} 个")

        return merged_stands

    def _detect_long_dwell_stands(self) -> List[Dict[str, Any]]:
        """方法1: 检测长时间停留的机位"""
        print("\n[1/3] 检测长时间停留（≥5分钟）...")

        long_dwell_candidates = []

        for callsign, trajectory in self.trajectories.items():
            # 找到所有低速段
            segments = self._extract_dwelling_segments(trajectory, speed_threshold=2.0)

            for segment in segments:
                duration = segment['duration']

                # 长时间停留（≥5分钟）
                if duration >= 300:  # 5分钟
                    long_dwell_candidates.append({
                        'callsign': callsign,
                        'lat': segment['lat'],
                        'lon': segment['lon'],
                        'duration': duration,
                        'point_count': segment['point_count'],
                        'detection_method': 'long_dwell',
                        'confidence': min(1.0, duration / 600),  # 停留时间越长置信度越高
                        'time_range': (segment['start_time'], segment['end_time'])
                    })

        print(f"  长时间停留候选: {len(long_dwell_candidates)} 个")

        # 对长时间停留进行聚类
        if long_dwell_candidates:
            stands = self._cluster_stands(long_dwell_candidates, method='long_dwell')
            return stands

        return []

    def _detect_short_dwell_stands(self) -> List[Dict[str, Any]]:
        """方法2: 检测短时间停留的聚类（传统方法）"""
        print("\n[2/3] 检测短时间停留聚类（30秒-5分钟）...")

        short_dwell_candidates = []

        for callsign, trajectory in self.trajectories.items():
            # 找到所有低速段
            segments = self._extract_dwelling_segments(trajectory, speed_threshold=2.0)

            for segment in segments:
                duration = segment['duration']

                # 短时间停留（30秒-5分钟）
                if 30 <= duration < 300:
                    short_dwell_candidates.append({
                        'callsign': callsign,
                        'lat': segment['lat'],
                        'lon': segment['lon'],
                        'duration': duration,
                        'point_count': segment['point_count'],
                        'detection_method': 'short_dwell_cluster'
                    })

        print(f"  短时间停留候选: {len(short_dwell_candidates)} 个")

        # 对短时间停留进行聚类（更严格的聚类半径）
        if short_dwell_candidates:
            stands = self._cluster_stands(short_dwell_candidates, method='short_dwell')
            return stands

        return []

    def _detect_stable_positions(self) -> List[Dict[str, Any]]:
        """方法3: 检测位置稳定性（减少GPS漂移干扰）"""
        print("\n[3/3] 检测位置稳定性（GPS漂移过滤）...")

        stable_positions = []

        for callsign, trajectory in self.trajectories.items():
            # 分析每个轨迹点周围是否有其他轨迹点
            for i, point in enumerate(trajectory):
                speed = point.get('groundspeed', 0)

                # 只看低速点（可能停留）
                if speed > 2.0:
                    continue

                # 检查周围空间是否有其他轨迹点（位置稳定性）
                nearby_count = self._count_nearby_points(
                    point, trajectory, radius_degrees=0.0001  # 约10米
                )

                # 检查时间连续性（连续低速点）
                time_consecutive = self._check_time_consecutive(point, trajectory)

                # 稳定性得分
                stability_score = min(1.0, (nearby_count / 10) * (time_consecutive / 5))

                if stability_score >= 0.5:  # 稳定性阈值
                    stable_positions.append({
                        'callsign': callsign,
                        'lat': point['LAT'],
                        'lon': point['LON'],
                        'speed': speed,
                        'nearby_count': nearby_count,
                        'time_consecutive': time_consecutive,
                        'stability_score': stability_score,
                        'detection_method': 'stability'
                    })

        print(f"  稳定位置候选: {len(stable_positions)} 个")

        # 对稳定位置进行聚类
        if stable_positions:
            stands = self._cluster_stands(stable_positions, method='stability')
            return stands

        return []

    def _extract_dwelling_segments(
        self,
        trajectory: List[Dict[str, Any]],
        speed_threshold: float = 2.0
    ) -> List[Dict[str, Any]]:
        """提取低速停留段"""
        segments = []
        current_segment = []

        for point in trajectory:
            speed = point.get('groundspeed', 0)
            if speed <= speed_threshold:
                current_segment.append(point)
            else:
                if len(current_segment) >= 3:  # 至少3个连续低速点
                    segments.append(self._analyze_segment(current_segment))
                current_segment = []

        # 处理最后一段
        if len(current_segment) >= 3:
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
        avg_speed = sum(p.get('groundspeed', 0) for p in segment) / len(segment)

        return {
            'lat': lat,
            'lon': lon,
            'duration': duration,
            'point_count': len(segment),
            'avg_speed': avg_speed,
            'start_time': segment[0]['TIME'],
            'end_time': segment[-1]['TIME']
        }

    def _count_nearby_points(
        self,
        point: Dict[str, Any],
        trajectory: List[Dict[str, Any]],
        radius_degrees: float = 0.0001
    ) -> int:
        """计算附近轨迹点数量"""
        lat = point['LAT']
        lon = point['LON']

        count = 0
        for other in trajectory:
            if other is point:
                continue

            # 计算距离（简化版）
            lat_diff = abs(other['LAT'] - lat)
            lon_diff = abs(other['LON'] - lon)

            if lat_diff < radius_degrees and lon_diff < radius_degrees:
                count += 1

        return count

    def _check_time_consecutive(
        self,
        point: Dict[str, Any],
        trajectory: List[Dict[str, Any]],
        max_gap_seconds: float = 5.0
    ) -> int:
        """检查时间连续性"""
        try:
            point_time = datetime.fromisoformat(point['TIME'])
        except:
            return 0

        consecutive_count = 0
        for other in trajectory:
            try:
                other_time = datetime.fromisoformat(other['TIME'])
                time_diff = abs((other_time - point_time).total_seconds())

                if time_diff <= max_gap_seconds:
                    consecutive_count += 1
            except:
                continue

        return consecutive_count

    def _cluster_stands(
        self,
        candidates: List[Dict[str, Any]],
        method: str
    ) -> List[Dict[str, Any]]:
        """聚类候选点为机位"""
        if not candidates:
            return []

        # 提取坐标
        coords = np.array([[c['lat'], c['lon']] for c in candidates])

        # DBSCAN聚类
        if method == 'long_dwell':
            # 长时间停留：聚类半径可以大一些（10米）
            eps = 0.0001
        elif method == 'short_dwell':
            # 短时间停留：聚类半径小一些（5米）
            eps = 0.00005
        else:  # stability
            # 稳定性检测：最小半径（3米）
            eps = 0.00003

        clustering = DBSCAN(eps=eps, min_samples=1).fit(coords)
        labels = clustering.labels_

        # 统计聚类
        clusters = defaultdict(list)
        for i, label in enumerate(labels):
            clusters[label].append(candidates[i])

        # 计算每个聚类的中心
        stands = []
        for label, points in clusters.items():
            # 计算加权中心（停留时间加权）
            if method in ['long_dwell', 'short_dwell']:
                # 按停留时间加权
                total_weight = sum(p.get('duration', 1) for p in points)
                if total_weight > 0:
                    avg_lat = sum(p['lat'] * p.get('duration', 1) for p in points) / total_weight
                    avg_lon = sum(p['lon'] * p.get('duration', 1) for p in points) / total_weight
                else:
                    avg_lat = sum(p['lat'] for p in points) / len(points)
                    avg_lon = sum(p['lon'] for p in points) / len(points)

                total_duration = sum(p.get('duration', 0) for p in points)
                avg_duration = total_duration / len(points)
            else:
                # 稳定性方法：按稳定性得分加权
                total_weight = sum(p.get('stability_score', 1) for p in points)
                if total_weight > 0:
                    avg_lat = sum(p['lat'] * p.get('stability_score', 1) for p in points) / total_weight
                    avg_lon = sum(p['lon'] * p.get('stability_score', 1) for p in points) / total_weight
                else:
                    avg_lat = sum(p['lat'] for p in points) / len(points)
                    avg_lon = sum(p['lon'] for p in points) / len(points)

                avg_duration = sum(p.get('duration', 0) for p in points) / len(points)

            stands.append({
                'id': f'enhanced_stand_{label}',
                'type': 'stand',
                'lat': avg_lat,
                'lon': avg_lon,
                'observations': len(points),
                'total_dwell_time': total_duration if method in ['long_dwell', 'short_dwell'] else sum(p.get('duration', 0) for p in points),
                'avg_dwell_time': avg_duration,
                'detection_methods': list(set(p.get('detection_method', 'unknown') for p in points))
            })

        return stands

    def _merge_duplicate_stands(self, stands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并重复的机位（相同位置的聚类合并）"""
        if len(stands) <= 1:
            return stands

        # 计算距离矩阵
        merged = []
        used = set()

        for i, stand1 in enumerate(stands):
            if i in used:
                continue

            # 找到所有相近的机位
            cluster = [stand1]
            for j, stand2 in enumerate(stands[i+1:], i+1):
                if j in used:
                    continue

                # 计算距离
                lat_diff = abs(stand1['lat'] - stand2['lat'])
                lon_diff = abs(stand1['lon'] - stand2['lon'])

                # 如果很近（<5米），认为是同一个机位
                if lat_diff < 0.00005 and lon_diff < 0.00005:
                    cluster.append(stand2)
                    used.add(j)

            used.add(i)

            # 合并聚类内的机位
            if len(cluster) > 1:
                # 计算加权中心
                total_obs = sum(s['observations'] for s in cluster)
                avg_lat = sum(s['lat'] * s['observations'] for s in cluster) / total_obs
                avg_lon = sum(s['lon'] * s['observations'] for s in cluster) / total_obs

                merged_stand = {
                    'id': cluster[0]['id'],
                    'type': 'stand',
                    'lat': avg_lat,
                    'lon': avg_lon,
                    'observations': total_obs,
                    'total_dwell_time': sum(s.get('total_dwell_time', 0) for s in cluster),
                    'avg_dwell_time': sum(s.get('avg_dwell_time', 0) for s in cluster) / len(cluster),
                    'detection_methods': list(set().union(*[s.get('detection_methods', ['unknown']) for s in cluster]))
                }
            else:
                merged_stand = cluster[0]

            merged.append(merged_stand)

        return merged


if __name__ == "__main__":
    # 示例使用
    print("增强版机位识别模块已创建")
    print("\n使用方法:")
    print("from enhanced_stand_detection import EnhancedStandDetector")
    print("\ndetector = EnhancedStandDetector()")
    print("stands = detector.detect_stands_from_trajectories(trajectories)")
