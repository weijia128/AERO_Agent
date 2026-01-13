#!/usr/bin/env python3
"""
AWOS气象数据提取和清洗脚本

从AWOS日志文件中提取风向、温度、气压等气象数据，
并进行数据清洗（处理缺失值///、null等）。

使用方法:
    python scripts/data_processing/extract_awos_weather.py

输出:
    data/processed/awos_weather_<date>.csv
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd


def extract_json_from_line(line: str) -> Optional[Dict]:
    """从日志行中提取JSON数据"""
    try:
        # 查找JSON开始的位置（第一个左大括号）
        json_start = line.find('{"id":')
        if json_start == -1:
            return None

        json_str = line[json_start:]
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def parse_timestamp(log_prefix: str) -> Optional[datetime]:
    """从日志前缀解析时间戳"""
    try:
        # 格式: "2026-01-06 05:00:25,937"
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', log_prefix)
        if match:
            return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
    return None


def clean_value(value: Any) -> Any:
    """
    清洗数据值
    - "///" -> None
    - null -> None
    - 0.0 在特定字段中表示无效，也转为None
    """
    if value == "///" or value is None:
        return None
    if isinstance(value, float) and value == 0.0:
        # 对于某些字段，0.0可能是无效值
        # 这里保留0.0，让调用者决定如何处理
        return value
    return value


def extract_wind_data(data: Dict) -> Dict[str, Any]:
    """提取WIND类型的数据"""
    return {
        'wind_direction': clean_value(data.get('wdins')),      # 主风向 (度)
        'wind_speed': clean_value(data.get('wsins')),          # 主风速 (m/s)
        'wind_direction_10m': clean_value(data.get('wd10m')),  # 10米风向
        'wind_speed_10m': clean_value(data.get('ws10m')),      # 10米风速
        'wind_direction_2m': clean_value(data.get('wd2m')),    # 2米风向
        'wind_speed_2m': clean_value(data.get('ws2m')),        # 2米风速
        'cross_wind_2a': clean_value(data.get('cw2a')),        # 横风分量
        'head_wind_2a': clean_value(data.get('hw2a')),         # 顺风/顶风分量
    }


def extract_humitemp_data(data: Dict) -> Dict[str, Any]:
    """提取HUMITEMP类型的数据"""
    return {
        'temperature': clean_value(data.get('tains')),         # 温度 (°C)
        'dew_point': clean_value(data.get('tdins')),           # 露点 (°C)
        'relative_humidity': clean_value(data.get('rhins')),   # 相对湿度 (%)
    }


def extract_press_data(data: Dict) -> Dict[str, Any]:
    """提取PRESS类型的数据"""
    return {
        'qnh': clean_value(data.get('qnhins')),                # QNH (hPa)
        'qfe': clean_value(data.get('qfeins')),                # QFE (hPa)
        'station_pressure': clean_value(data.get('pains')),    # 站压 (hPa)
    }


def extract_vis_data(data: Dict) -> Dict[str, Any]:
    """提取VIS类型的数据（可选）"""
    return {
        'visibility': clean_value(data.get('vis')),            # 能见度 (m)
        'rvr': clean_value(data.get('rvr')),                   # RVR (m)
    }


def process_awos_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    处理单个AWOS日志文件

    Args:
        file_path: AWOS日志文件路径

    Returns:
        提取的气象数据记录列表
    """
    records = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 提取时间戳
            timestamp = parse_timestamp(line)
            if not timestamp:
                continue

            # 提取JSON数据
            json_data = extract_json_from_line(line)
            if not json_data:
                continue

            # 获取消息类型和位置
            header = json_data.get('header', {})
            message_type = header.get('messageType', '')
            location_id = header.get('locationId', '')

            # 只处理WIND、HUMITEMP、PRESS、VIS类型
            if message_type not in ['WIND', 'HUMITEMP', 'PRESS', 'VIS']:
                continue

            # 提取数据
            data = json_data.get('data', {})

            # 创建基础记录
            record = {
                'timestamp': timestamp,
                'location_id': location_id,
                'message_type': message_type,
            }

            # 根据消息类型提取对应字段
            if message_type == 'WIND':
                record.update(extract_wind_data(data))
            elif message_type == 'HUMITEMP':
                record.update(extract_humitemp_data(data))
            elif message_type == 'PRESS':
                record.update(extract_press_data(data))
            elif message_type == 'VIS':
                record.update(extract_vis_data(data))

            records.append(record)

    return records


def merge_weather_records(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    将不同类型的气象记录合并成统一表格

    策略：
    1. 对每个timestamp+location_id组合，收集所有类型的数据
    2. 将同一时刻的不同类型数据合并到一行
    """
    if not records:
        return pd.DataFrame()

    # 转换为DataFrame
    df = pd.DataFrame(records)

    # 按timestamp和location_id分组，聚合所有字段
    # 使用first()取每个字段的第一个非空值
    grouped = df.groupby(['timestamp', 'location_id']).agg({
        col: lambda x: x.dropna().first_valid_index() and x.loc[x.dropna().first_valid_index()] if x.dropna().size > 0 else None
        for col in df.columns
        if col not in ['timestamp', 'location_id', 'message_type']
    }).reset_index()

    return grouped


def process_all_awos_files(input_dir: Path, output_dir: Path) -> None:
    """
    处理所有AWOS日志文件

    Args:
        input_dir: 输入目录（包含AWOS日志文件）
        output_dir: 输出目录（保存处理后的CSV）
    """
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 查找所有AWOS日志文件
    awos_files = sorted(input_dir.glob('AWOS_*.log'))

    if not awos_files:
        print(f"❌ 在 {input_dir} 中未找到AWOS日志文件")
        return

    print(f"📂 找到 {len(awos_files)} 个AWOS日志文件")

    # 处理每个文件
    all_records = []

    for file_path in awos_files:
        print(f"⏳ 处理: {file_path.name}")
        records = process_awos_file(file_path)
        all_records.extend(records)
        print(f"   ✅ 提取了 {len(records)} 条记录")

    if not all_records:
        print("❌ 未提取到任何气象数据")
        return

    # 合并记录
    print(f"\n🔀 合并 {len(all_records)} 条记录...")
    df_merged = merge_weather_records(all_records)

    # 保存为CSV
    output_file = output_dir / f"awos_weather_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df_merged.to_csv(output_file, index=False, encoding='utf-8-sig')

    print(f"\n✅ 数据已保存到: {output_file}")
    print(f"   总计 {len(df_merged)} 条合并后的记录")
    print(f"   涵盖 {df_merged['location_id'].nunique()} 个位置")

    # 打印统计信息
    print("\n📊 数据统计:")
    print(f"   时间范围: {df_merged['timestamp'].min()} ~ {df_merged['timestamp'].max()}")
    print(f"   位置列表: {', '.join(sorted(df_merged['location_id'].unique()))}")

    # 各字段的数据完整性
    print("\n📈 字段完整性:")
    for col in df_merged.columns:
        if col not in ['timestamp', 'location_id']:
            non_null_count = df_merged[col].notna().sum()
            pct = (non_null_count / len(df_merged)) * 100
            print(f"   {col}: {non_null_count}/{len(df_merged)} ({pct:.1f}%)")


def main():
    """主函数"""
    # 定义路径
    base_dir = Path(__file__).parent.parent.parent
    input_dir = base_dir / 'data' / 'raw' / '气象数据'
    output_dir = base_dir / 'data' / 'processed'

    print("=" * 60)
    print("🌤️  AWOS气象数据提取和清洗工具")
    print("=" * 60)
    print()

    # 检查输入目录
    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        return

    # 处理所有AWOS文件
    process_all_awos_files(input_dir, output_dir)

    print()
    print("=" * 60)
    print("✅ 处理完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
