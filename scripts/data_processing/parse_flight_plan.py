"""
航班计划数据解析器

解析格式：
[2025-10-21 10:31:6:328]{"inorout":"A", "callsign":"CES2146", ...}
"""
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class FlightPlanParser:
    """航班计划解析器"""

    def __init__(self):
        self.pattern = re.compile(r'\[([^\]]+)\]\s*(\{.*\})')

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行数据"""
        line = line.strip()
        if not line:
            return None

        match = self.pattern.match(line)
        if not match:
            return None

        timestamp_str, json_str = match.groups()

        try:
            # 解析JSON数据
            data = json.loads(json_str)

            # 添加日志时间戳
            data['log_timestamp'] = timestamp_str

            # 清理空字符串为None
            for key in ['aldt', 'atot', 'eldt', 'etot', 'runway', 'stand']:
                if key in data and data[key] == "":
                    data[key] = None

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

    def parse_directory(self, dir_path: str, pattern: str = "*.txt") -> List[Dict[str, Any]]:
        """解析目录下所有符合模式的文件"""
        all_data = []
        for file_path in Path(dir_path).glob(pattern):
            print(f"解析文件: {file_path.name}")
            data = self.parse_file(str(file_path))
            all_data.extend(data)
        print(f"总共解析 {len(all_data)} 条记录")
        return all_data


def filter_by_time_range(
    data: List[Dict[str, Any]],
    start_time: str,
    end_time: str,
    time_field: str = "eldt"
) -> List[Dict[str, Any]]:
    """
    按时间范围筛选数据

    Args:
        data: 航班计划数据列表
        start_time: 开始时间 "2025-10-21 11:00:00"
        end_time: 结束时间 "2025-10-21 12:00:00"
        time_field: 用于筛选的时间字段 (eldt/etot/aldt/atot)
    """
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    filtered = []
    for record in data:
        time_str = record.get(time_field)
        if not time_str:
            continue

        try:
            record_dt = datetime.fromisoformat(time_str)
            if start_dt <= record_dt < end_dt:
                filtered.append(record)
        except (ValueError, TypeError):
            continue

    return filtered


def group_by_stand(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按机位分组"""
    groups = {}
    for record in data:
        stand = record.get('stand')
        if stand:
            if stand not in groups:
                groups[stand] = []
            groups[stand].append(record)
    return groups


def group_by_runway(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按跑道分组"""
    groups = {}
    for record in data:
        runway = record.get('runway')
        if runway:
            if runway not in groups:
                groups[runway] = []
            groups[runway].append(record)
    return groups


def calculate_statistics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算统计信息"""
    total = len(data)
    arrivals = sum(1 for r in data if r.get('inorout') == 'A')
    departures = sum(1 for r in data if r.get('inorout') == 'D')

    # 机位统计
    stands = {}
    for record in data:
        stand = record.get('stand')
        if stand:
            stands[stand] = stands.get(stand, 0) + 1

    # 跑道统计
    runways = {}
    for record in data:
        runway = record.get('runway')
        if runway:
            runways[runway] = runways.get(runway, 0) + 1

    return {
        'total_flights': total,
        'arrivals': arrivals,
        'departures': departures,
        'unique_stands': len(stands),
        'unique_runways': len(runways),
        'stand_usage': stands,
        'runway_usage': runways,
        'busiest_stand': max(stands.items(), key=lambda x: x[1]) if stands else None,
        'busiest_runway': max(runways.items(), key=lambda x: x[1]) if runways else None,
    }


if __name__ == "__main__":
    # 测试解析
    parser = FlightPlanParser()

    # 解析单个文件
    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "data" / "raw" / "航班计划"
    data = parser.parse_directory(data_dir, pattern="Log_*.txt")

    # 筛选 11:00-12:00 时段
    filtered = filter_by_time_range(
        data,
        "2025-10-21 11:00:00",
        "2025-10-21 12:00:00",
        time_field="eldt"  # 使用预计时间
    )

    print(f"\n11:00-12:00 时段航班数: {len(filtered)}")

    # 统计信息
    stats = calculate_statistics(filtered)
    print(f"\n统计信息:")
    print(f"- 总航班数: {stats['total_flights']}")
    print(f"- 到达: {stats['arrivals']}, 起飞: {stats['departures']}")
    print(f"- 使用机位数: {stats['unique_stands']}")
    print(f"- 使用跑道数: {stats['unique_runways']}")
    print(f"- 最繁忙机位: {stats['busiest_stand']}")
    print(f"- 最繁忙跑道: {stats['busiest_runway']}")
