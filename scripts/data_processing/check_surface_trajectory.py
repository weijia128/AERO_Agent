"""
检查航迹数据中是否包含场面滑行轨迹
"""
import json
import re
from pathlib import Path
from collections import defaultdict


def parse_trajectory_line(line):
    """解析航迹数据行"""
    pattern = re.compile(r'^([0-9:\- ]+),(\d+)\((\d+)\)\s+(\{.*\})$')
    match = pattern.match(line.strip())
    if not match:
        return None

    try:
        _, _, _, json_str = match.groups()
        return json.loads(json_str)
    except:
        return None


def check_surface_data(file_path, max_lines=10000):
    """检查场面数据特征"""
    print(f"\n检查文件: {Path(file_path).name}")
    print("=" * 60)

    aircraft_records = []
    surface_candidates = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break

            data = parse_trajectory_line(line)
            if not data or data.get('targettype') != 'Aircraft':
                continue

            aircraft_records.append(data)

            # 场面特征判断
            alt = data.get('ALT') or 0
            groundspeed = data.get('groundspeed') or 0
            stand = data.get('stand', '').strip() if data.get('stand') else ''
            runway = data.get('runway', '').strip() if data.get('runway') else ''

            # 低高度 + 低速度 + 有机位或跑道信息 = 可能是场面滑行
            if alt < 1000 and groundspeed > 0 and groundspeed < 50:
                surface_candidates.append(data)

    print(f"\n总飞机记录数: {len(aircraft_records)}")
    print(f"疑似场面滑行记录数: {len(surface_candidates)}")

    if surface_candidates:
        print(f"\n场面滑行数据样例（前5条）:")
        for i, record in enumerate(surface_candidates[:5]):
            print(f"\n样例 {i+1}:")
            print(f"  呼号: {record.get('CALLSIGN')}")
            print(f"  高度: {record.get('ALT')} 米")
            print(f"  地速: {record.get('groundspeed')} m/s")
            print(f"  航向: {record.get('heading')}")
            print(f"  机位: {record.get('stand')}")
            print(f"  跑道: {record.get('runway')}")
            print(f"  坐标: ({record.get('LAT')}, {record.get('LON')})")
            print(f"  时间: {record.get('TIME')}")

    # 按呼号分组，查看是否有连续轨迹
    if surface_candidates:
        print(f"\n检查连续滑行轨迹:")
        by_callsign = defaultdict(list)
        for rec in surface_candidates[:200]:  # 只看前200条
            callsign = rec.get('CALLSIGN')
            if callsign:
                by_callsign[callsign].append(rec)

        # 找出轨迹点最多的航班
        sorted_flights = sorted(by_callsign.items(), key=lambda x: len(x[1]), reverse=True)

        for i, (callsign, points) in enumerate(sorted_flights[:3]):
            print(f"\n航班 {callsign}: {len(points)} 个轨迹点")
            if len(points) >= 3:
                print(f"  起始: {points[0].get('TIME')} | 坐标: ({points[0].get('LAT'):.5f}, {points[0].get('LON'):.5f})")
                print(f"  中间: {points[len(points)//2].get('TIME')} | 坐标: ({points[len(points)//2].get('LAT'):.5f}, {points[len(points)//2].get('LON'):.5f})")
                print(f"  结束: {points[-1].get('TIME')} | 坐标: ({points[-1].get('LAT'):.5f}, {points[-1].get('LON'):.5f})")
                print(f"  机位变化: {points[0].get('stand')} → {points[-1].get('stand')}")
                print(f"  跑道: {points[0].get('runway')} → {points[-1].get('runway')}")

    # 高度分布统计
    print(f"\n高度分布统计:")
    alt_ranges = {
        '0-500m (场面)': 0,
        '500-1500m (起降)': 0,
        '1500-5000m (爬升/下降)': 0,
        '5000m+ (巡航)': 0
    }

    for rec in aircraft_records:
        alt = rec.get('ALT') or 0
        if alt < 500:
            alt_ranges['0-500m (场面)'] += 1
        elif alt < 1500:
            alt_ranges['500-1500m (起降)'] += 1
        elif alt < 5000:
            alt_ranges['1500-5000m (爬升/下降)'] += 1
        else:
            alt_ranges['5000m+ (巡航)'] += 1

    for range_name, count in alt_ranges.items():
        percentage = count / len(aircraft_records) * 100 if aircraft_records else 0
        print(f"  {range_name}: {count} 条 ({percentage:.1f}%)")

    return len(surface_candidates) > 0


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    traj_dir = project_root / "data" / "raw" / "航迹数据"

    # 检查11点的数据
    has_surface = check_surface_data(traj_dir / "2025-10-21_11h.log", max_lines=50000)

    if has_surface:
        print("\n" + "=" * 60)
        print("✓ 航迹数据中包含场面滑行轨迹！")
        print("可以进行滑行路径重建")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ 航迹数据中可能不包含详细的场面滑行轨迹")
        print("需要采用替代方案")
        print("=" * 60)
