"""
EFS 航班计划数据解析器

解析格式：
2026-01-06 08:01:50,856(658940467) INFO  RocketMQConsumer - rev ID:...,{"id":"...","system":"EFS","dataType":"IFPL","data":{...}}

说明：
- EFS 格式是嵌套 JSON，实际航班数据在 data 字段中
- 需要映射字段名到旧格式兼容的字段名
"""
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class EFSFlightPlanParser:
    """EFS 航班计划解析器"""

    def __init__(self, airport_code: str = "ZLXY"):
        """
        Args:
            airport_code: 机场代码，用于判断进出港方向
        """
        self.airport_code = airport_code
        # 匹配 JSON 部分（从第一个 { 开始到行尾）
        self.json_pattern = re.compile(r'\{.*\}')

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行数据"""
        line = line.strip()
        if not line:
            return None

        try:
            # 提取 JSON 部分
            match = self.json_pattern.search(line)
            if not match:
                return None

            json_str = match.group(0)
            envelope = json.loads(json_str)

            # 检查是否是 EFS IFPL 数据
            if envelope.get('system') != 'EFS' or envelope.get('dataType') != 'IFPL':
                return None

            # 提取实际航班数据
            flight_data = envelope.get('data', {})
            if not flight_data:
                return None

            # 转换为统一格式
            normalized = self._normalize_fields(flight_data)

            # 添加元数据
            normalized['source_format'] = 'EFS'
            normalized['raw_id'] = envelope.get('id')

            return normalized

        except (json.JSONDecodeError, KeyError) as e:
            # 静默跳过解析错误的行
            return None

    def _normalize_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 EFS 字段映射为统一格式

        字段映射:
        - callsign: 保持不变
        - stand: 保持不变
        - runway: arr_runway_name (到达) / dep_runway_name (出发)
        - eldt: 保持不变 (预计着陆时间)
        - etot: eobt (预计起飞准备时间)
        - aldt: aldt (实际着陆时间)
        - atot: 保持不变 (实际起飞时间)
        - inorout: 根据 p_dep_ap 和 p_arr_ap 推断
        """
        normalized = {}

        # 基础字段
        normalized['callsign'] = data.get('callsign')
        normalized['stand'] = data.get('stand')
        normalized['aircraft_type'] = data.get('aircraft_type')
        normalized['reg_number'] = data.get('reg_number')

        # 判断进出港方向
        p_dep_ap = data.get('p_dep_ap')  # 计划起飞机场
        p_arr_ap = data.get('p_arr_ap')  # 计划到达机场

        if p_arr_ap == self.airport_code:
            # 到达航班
            normalized['inorout'] = 'A'
            normalized['runway'] = data.get('arr_runway_name') or data.get('runway')
        elif p_dep_ap == self.airport_code:
            # 出发航班
            normalized['inorout'] = 'D'
            normalized['runway'] = data.get('dep_runway_name') or data.get('runway')
        else:
            # 无法判断，默认为到达
            normalized['inorout'] = 'A'
            normalized['runway'] = data.get('arr_runway_name') or data.get('dep_runway_name')

        # 时间字段
        normalized['eldt'] = data.get('eldt')  # 预计着陆
        normalized['etot'] = data.get('eobt')  # 预计起飞（EFS 中叫 eobt）
        normalized['aldt'] = data.get('aldt')  # 实际着陆
        normalized['atot'] = data.get('atot')  # 实际起飞

        # 清理空字符串
        for key in ['runway', 'stand', 'eldt', 'etot', 'aldt', 'atot']:
            if key in normalized and normalized[key] == "":
                normalized[key] = None

        # 额外信息
        normalized['dep_airport'] = p_dep_ap
        normalized['arr_airport'] = p_arr_ap
        normalized['strip_status'] = data.get('strip_status')
        normalized['squawk_code'] = data.get('squawk_code')

        return normalized

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

    def parse_directory(
        self,
        dir_path: str,
        pattern: str = "EFS_*.log"
    ) -> List[Dict[str, Any]]:
        """解析目录下所有符合模式的文件"""
        all_data = []
        for file_path in sorted(Path(dir_path).glob(pattern)):
            print(f"解析文件: {file_path.name}")
            data = self.parse_file(str(file_path))
            all_data.extend(data)
            print(f"  - 解析 {len(data)} 条记录")
        print(f"总共解析 {len(all_data)} 条记录")
        return all_data


def filter_by_time_range(
    data: List[Dict[str, Any]],
    start_time: str,
    end_time: str,
    time_fields: List[str] = None
) -> List[Dict[str, Any]]:
    """
    按时间范围筛选数据

    Args:
        data: 航班计划数据列表
        start_time: 开始时间 "2026-01-06 08:00:00"
        end_time: 结束时间 "2026-01-06 12:00:00"
        time_fields: 用于筛选的时间字段列表（任一字段在范围内即可）
    """
    if time_fields is None:
        time_fields = ['eldt', 'etot', 'aldt', 'atot']

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    filtered = []
    for record in data:
        # 只要任一时间字段在范围内就保留该记录
        match = False
        for field in time_fields:
            time_str = record.get(field)
            if not time_str:
                continue

            try:
                record_dt = datetime.fromisoformat(time_str)
                if start_dt <= record_dt < end_dt:
                    match = True
                    break
            except (ValueError, TypeError):
                continue

        if match:
            filtered.append(record)

    return filtered


def merge_and_save(
    input_dir: str,
    output_file: str,
    pattern: str = "EFS_2026-01-06_*h_filtered.log",
    time_range: tuple = None
) -> int:
    """
    合并多个 EFS 文件并保存为统一格式

    Args:
        input_dir: 输入目录
        output_file: 输出文件路径
        pattern: 文件匹配模式
        time_range: 可选的时间范围过滤 (start_time, end_time)

    Returns:
        保存的记录数
    """
    parser = EFSFlightPlanParser()

    # 解析所有文件
    all_data = parser.parse_directory(input_dir, pattern)

    # 可选时间过滤
    if time_range:
        start_time, end_time = time_range
        all_data = filter_by_time_range(all_data, start_time, end_time)
        print(f"时间过滤后: {len(all_data)} 条记录")

    # 按时间排序
    all_data.sort(key=lambda x: x.get('eldt') or x.get('etot') or '')

    # 保存为标准格式（兼容旧解析器）
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        for record in all_data:
            # 使用旧格式的时间戳占位符
            timestamp = record.get('eldt') or record.get('etot') or '2026-01-06 00:00:00'
            # 只保留关键字段
            compact = {
                'callsign': record.get('callsign'),
                'inorout': record.get('inorout'),
                'stand': record.get('stand'),
                'runway': record.get('runway'),
                'eldt': record.get('eldt'),
                'etot': record.get('etot'),
                'aldt': record.get('aldt'),
                'atot': record.get('atot'),
                'aircraft_type': record.get('aircraft_type'),
            }
            line = f"[{timestamp}] {json.dumps(compact, ensure_ascii=False)}\n"
            f.write(line)

    print(f"已保存 {len(all_data)} 条记录到: {output_file}")
    return len(all_data)


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
    """
    使用示例：合并 2026-01-06 8:00-12:00 的数据
    """
    project_root = Path(__file__).resolve().parents[2]
    input_dir = project_root / "data" / "raw" / "航班计划"
    output_file = project_root / "data" / "raw" / "航班计划" / "Flight_Plan_2026-01-06_08-12.txt"

    print("=" * 60)
    print("开始合并 EFS 航班计划数据")
    print("=" * 60)

    # 合并数据（移除时间过滤，保留所有数据）
    count = merge_and_save(
        str(input_dir),
        str(output_file),
        pattern="EFS_2026-01-06_*h_filtered.log",
        time_range=None  # 不过滤时间，保留所有数据
    )

    print("\n" + "=" * 60)
    print(f"✓ 成功合并 {count} 条航班记录")
    print(f"✓ 输出文件: {output_file}")
    print("=" * 60)

    # 统计信息
    parser = EFSFlightPlanParser()
    data = parser.parse_file(str(output_file))
    stats = calculate_statistics(data)

    print(f"\n航班统计:")
    print(f"  总航班数: {stats['total_flights']}")
    print(f"  到达: {stats['arrivals']} | 出发: {stats['departures']}")
    print(f"  使用机位数: {stats['unique_stands']}")
    print(f"  使用跑道数: {stats['unique_runways']}")
    if stats['busiest_stand']:
        print(f"  最繁忙机位: {stats['busiest_stand'][0]} ({stats['busiest_stand'][1]} 架次)")
    if stats['busiest_runway']:
        print(f"  最繁忙跑道: {stats['busiest_runway'][0]} ({stats['busiest_runway'][1]} 架次)")
