"""
航迹数据解析器

解析格式：
2025-10-21 11:00:00,007(237573874)  {"TIMEOFTRACK":1761015602750, "CALLSIGN":"CES2796", ...}
"""
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict


class TrajectoryParser:
    """航迹数据解析器"""

    def __init__(self):
        # 匹配时间戳和JSON数据
        self.pattern = re.compile(r'^([0-9:\- ]+),(\d+)\((\d+)\)\s+(\{.*\})$')

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行航迹数据"""
        line = line.strip()
        if not line:
            return None

        match = self.pattern.match(line)
        if not match:
            return None

        timestamp_str, millisec, track_id, json_str = match.groups()

        try:
            # 解析JSON数据
            data = json.loads(json_str)

            # 添加日志时间戳
            data['log_timestamp'] = timestamp_str
            data['log_millisec'] = int(millisec)
            data['log_track_id'] = int(track_id)

            # 清理空字符串
            for key in ['runway', 'stand', 'CALLSIGN', 'ICAO24', 'ssr']:
                if key in data and data[key] == "":
                    data[key] = None

            # 提取机位号（去除空格）
            if data.get('stand'):
                data['stand'] = data['stand'].strip()

            return data
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {line[:100]} | {e}")
            return None

    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """解析整个文件"""
        results = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                parsed = self.parse_line(line)
                if parsed:
                    parsed['line_no'] = line_no
                    parsed['source_file'] = Path(file_path).name
                    results.append(parsed)
        return results

    def parse_directory(self, dir_path: str, pattern: str = "*.log") -> List[Dict[str, Any]]:
        """解析目录下所有符合模式的文件"""
        all_data = []
        for file_path in sorted(Path(dir_path).glob(pattern)):
            print(f"解析文件: {file_path.name}")
            data = self.parse_file(str(file_path))
            all_data.extend(data)
        print(f"总共解析 {len(all_data)} 条航迹记录")
        return all_data


def filter_by_time_range(
    data: List[Dict[str, Any]],
    start_time: str,
    end_time: str
) -> List[Dict[str, Any]]:
    """按时间范围筛选航迹数据"""
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    filtered = []
    for record in data:
        time_str = record.get('TIME')
        if not time_str:
            continue

        try:
            record_dt = datetime.fromisoformat(time_str)
            if start_dt <= record_dt < end_dt:
                filtered.append(record)
        except (ValueError, TypeError):
            continue

    return filtered


def filter_aircraft_only(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """只保留飞机数据（排除车辆）"""
    return [r for r in data if r.get('targettype') == 'Aircraft']


def group_by_callsign(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按航班呼号分组（构建轨迹序列）"""
    groups = defaultdict(list)
    for record in data:
        callsign = record.get('CALLSIGN')
        if callsign:
            groups[callsign].append(record)

    # 每个航班的轨迹按时间排序
    for callsign in groups:
        groups[callsign].sort(key=lambda x: x.get('TIME', ''))

    return dict(groups)


def extract_stand_runway_mapping(data: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """
    提取机位-跑道映射关系

    返回格式：
    {
        "506": {"05L": 15, "05R": 2},  # 506机位使用05L跑道15次，05R跑道2次
        ...
    }
    """
    mapping = defaultdict(lambda: defaultdict(int))

    for record in data:
        stand = record.get('stand')
        runway = record.get('runway')
        if stand and runway:
            mapping[stand][runway] += 1

    return {k: dict(v) for k, v in mapping.items()}


def extract_trajectories(
    data: List[Dict[str, Any]],
    callsign: str
) -> List[Dict[str, Any]]:
    """提取特定航班的完整轨迹"""
    trajectory = [r for r in data if r.get('CALLSIGN') == callsign]
    trajectory.sort(key=lambda x: x.get('TIME', ''))
    return trajectory


def calculate_trajectory_stats(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算航迹统计信息"""
    aircraft_only = filter_aircraft_only(data)

    # 唯一航班数
    callsigns = set(r.get('CALLSIGN') for r in aircraft_only if r.get('CALLSIGN'))

    # 机位使用统计
    stands_used = defaultdict(int)
    for record in aircraft_only:
        stand = record.get('stand')
        if stand:
            stands_used[stand] += 1

    # 跑道使用统计
    runways_used = defaultdict(int)
    for record in aircraft_only:
        runway = record.get('runway')
        if runway:
            runways_used[runway] += 1

    # 机位-跑道映射
    stand_runway_map = extract_stand_runway_mapping(aircraft_only)

    return {
        'total_records': len(data),
        'aircraft_records': len(aircraft_only),
        'unique_flights': len(callsigns),
        'unique_stands': len(stands_used),
        'unique_runways': len(runways_used),
        'stand_usage': dict(stands_used),
        'runway_usage': dict(runways_used),
        'stand_runway_mapping': stand_runway_map,
    }


if __name__ == "__main__":
    # 测试解析
    parser = TrajectoryParser()

    # 解析航迹数据
    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "data" / "raw" / "航迹数据"
    data = parser.parse_file(data_dir / "2025-10-21_11h.log")

    print(f"解析完成: {len(data)} 条记录")

    # 筛选 11:00-12:00 时段
    filtered = filter_by_time_range(
        data,
        "2025-10-21 11:00:00",
        "2025-10-21 12:00:00"
    )

    print(f"\n11:00-12:00 时段航迹记录数: {len(filtered)}")

    # 只保留飞机
    aircraft = filter_aircraft_only(filtered)
    print(f"飞机记录数: {len(aircraft)}")

    # 统计信息
    stats = calculate_trajectory_stats(filtered)
    print(f"\n统计信息:")
    print(f"- 总记录数: {stats['total_records']}")
    print(f"- 飞机记录数: {stats['aircraft_records']}")
    print(f"- 唯一航班数: {stats['unique_flights']}")
    print(f"- 涉及机位数: {stats['unique_stands']}")
    print(f"- 涉及跑道数: {stats['unique_runways']}")

    # 机位-跑道映射
    print(f"\n机位-跑道映射关系（前10个）:")
    for i, (stand, runways) in enumerate(list(stats['stand_runway_mapping'].items())[:10]):
        print(f"  {stand}: {runways}")
