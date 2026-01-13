#!/usr/bin/env python3
"""
AWOS气象数据分析脚本

对提取的气象数据进行统计分析，生成报告和可视化图表。

使用方法:
    python scripts/data_processing/analyze_awos_weather.py

输出:
    - data/processed/awos_analysis_report.txt: 文本分析报告
    - data/processed/awos_per_location/: 按位置分离的CSV文件
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json


def load_weather_data(csv_path: Path) -> pd.DataFrame:
    """加载气象数据CSV"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def generate_statistics(df: pd.DataFrame, field: str) -> Dict:
    """生成单个字段的统计信息"""
    series = df[field].dropna()

    if len(series) == 0:
        return {
            'count': 0,
            'missing': len(df),
            'missing_pct': 100.0
        }

    return {
        'count': len(series),
        'missing': df[field].isna().sum(),
        'missing_pct': (df[field].isna().sum() / len(df)) * 100,
        'min': float(series.min()) if series.dtype in ['float64', 'int64'] else None,
        'max': float(series.max()) if series.dtype in ['float64', 'int64'] else None,
        'mean': float(series.mean()) if series.dtype in ['float64', 'int64'] else None,
        'std': float(series.std()) if series.dtype in ['float64', 'int64'] else None,
    }


def generate_location_report(df: pd.DataFrame, location_id: str) -> str:
    """生成单个位置的报告"""
    df_loc = df[df['location_id'] == location_id]

    if len(df_loc) == 0:
        return f"\n## 位置 {location_id}: 无数据\n"

    report = f"\n## 位置 {location_id}\n"
    report += f"  数据记录数: {len(df_loc)}\n"
    report += f"  时间范围: {df_loc['timestamp'].min()} ~ {df_loc['timestamp'].max()}\n"
    report += f"  时间跨度: {(df_loc['timestamp'].max() - df_loc['timestamp'].min()).total_seconds() / 3600:.1f} 小时\n\n"

    # 统计各字段
    fields_to_analyze = [
        ('温度 (°C)', 'temperature'),
        ('露点 (°C)', 'dew_point'),
        ('相对湿度 (%)', 'relative_humidity'),
        ('能见度 (m)', 'visibility'),
        ('RVR (m)', 'rvr'),
        ('QNH (hPa)', 'qnh'),
        ('QFE (hPa)', 'qfe'),
        ('站压 (hPa)', 'station_pressure'),
        ('风向 (度)', 'wind_direction'),
        ('风速 (m/s)', 'wind_speed'),
        ('10米风向 (度)', 'wind_direction_10m'),
        ('10米风速 (m/s)', 'wind_speed_10m'),
        ('2米风向 (度)', 'wind_direction_2m'),
        ('2米风速 (m/s)', 'wind_speed_2m'),
        ('横风分量 (m/s)', 'cross_wind_2a'),
        ('顶风分量 (m/s)', 'head_wind_2a'),
    ]

    report += "  字段统计:\n"
    for label, field in fields_to_analyze:
        if field in df_loc.columns:
            stats = generate_statistics(df_loc, field)
            if stats['count'] > 0 and stats['mean'] is not None:
                report += f"    {label:20s}: {stats['count']:4d} 条记录, "
                report += f"范围 [{stats['min']:.1f}, {stats['max']:.1f}], "
                report += f"平均 {stats['mean']:.1f}±{stats['std']:.1f}, "
                report += f"缺失率 {stats['missing_pct']:.1f}%\n"
            else:
                report += f"    {label:20s}: {stats['count']:4d} 条记录, "
                report += f"缺失率 {stats['missing_pct']:.1f}%\n"

    return report


def split_by_location(df: pd.DataFrame, output_dir: Path) -> None:
    """按位置分离数据并保存为独立CSV文件"""
    loc_dir = output_dir / 'awos_per_location'
    loc_dir.mkdir(parents=True, exist_ok=True)

    locations = sorted(df['location_id'].unique())

    print(f"\n📁 按位置分离数据...")

    for location_id in locations:
        df_loc = df[df['location_id'] == location_id]
        output_file = loc_dir / f"awos_{location_id}.csv"
        df_loc.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"   ✅ {location_id}: {len(df_loc)} 条记录 -> {output_file.name}")


def generate_summary_report(df: pd.DataFrame) -> str:
    """生成总体统计报告"""
    report = "=" * 80 + "\n"
    report += "AWOS气象数据分析报告\n"
    report += "=" * 80 + "\n\n"

    report += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"数据时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}\n"
    report += f"总记录数: {len(df)}\n"
    report += f"位置数量: {df['location_id'].nunique()}\n"
    report += f"位置列表: {', '.join(sorted(df['location_id'].unique()))}\n\n"

    # 总体统计
    report += "## 总体字段统计\n\n"

    fields_to_analyze = [
        ('temperature', '温度 (°C)'),
        ('dew_point', '露点 (°C)'),
        ('relative_humidity', '相对湿度 (%)'),
        ('visibility', '能见度 (m)'),
        ('rvr', 'RVR (m)'),
        ('qnh', 'QNH (hPa)'),
        ('qfe', 'QFE (hPa)'),
        ('station_pressure', '站压 (hPa)'),
        ('wind_direction', '风向 (度)'),
        ('wind_speed', '风速 (m/s)'),
        ('wind_direction_10m', '10米风向 (度)'),
        ('wind_speed_10m', '10米风速 (m/s)'),
        ('wind_direction_2m', '2米风向 (度)'),
        ('wind_speed_2m', '2米风速 (m/s)'),
        ('cross_wind_2a', '横风分量 (m/s)'),
        ('head_wind_2a', '顶风分量 (m/s)'),
    ]

    for field, label in fields_to_analyze:
        if field in df.columns:
            stats = generate_statistics(df, field)
            report += f"{label:20s}: "
            report += f"有效 {stats['count']:4d}/{len(df):4d} ({100-stats['missing_pct']:5.1f}%), "
            if stats['mean'] is not None:
                report += f"范围 [{stats['min']:7.1f}, {stats['max']:7.1f}], "
                report += f"平均 {stats['mean']:7.1f}±{stats['std']:5.1f}\n"
            else:
                report += "\n"

    report += "\n"

    # 按位置统计
    report += "## 按位置详细统计\n"
    for location_id in sorted(df['location_id'].unique()):
        report += generate_location_report(df, location_id)

    return report


def detect_data_quality_issues(df: pd.DataFrame) -> List[str]:
    """检测数据质量问题"""
    issues = []

    # 检查1: 温度异常值
    if 'temperature' in df.columns:
        temp_extreme = df[(df['temperature'] < -50) | (df['temperature'] > 50)]
        if len(temp_extreme) > 0:
            issues.append(f"⚠️  发现 {len(temp_extreme)} 条温度异常值记录（<-50°C或>50°C）")

    # 检查2: 风速异常值
    if 'wind_speed' in df.columns:
        wind_extreme = df[df['wind_speed'] > 50]
        if len(wind_extreme) > 0:
            issues.append(f"⚠️  发现 {len(wind_extreme)} 条风速异常值记录（>50 m/s）")

    # 检查3: 相对湿度超出范围
    if 'relative_humidity' in df.columns:
        rh_invalid = df[(df['relative_humidity'] < 0) | (df['relative_humidity'] > 100)]
        if len(rh_invalid) > 0:
            issues.append(f"⚠️  发现 {len(rh_invalid)} 条相对湿度无效记录（<0%或>100%）")

    # 检查4: 气压异常值
    if 'qnh' in df.columns:
        qnh_extreme = df[(df['qnh'] < 800) | (df['qnh'] > 1100)]
        if len(qnh_extreme) > 0:
            issues.append(f"⚠️  发现 {len(qnh_extreme)} 条QNH气压异常值记录（<800 hPa或>1100 hPa）")

    return issues


def main():
    """主函数"""
    base_dir = Path(__file__).parent.parent.parent
    processed_dir = base_dir / 'data' / 'processed'

    # 查找最新的气象数据CSV
    csv_files = sorted(processed_dir.glob('awos_weather_*.csv'))
    if not csv_files:
        print("❌ 未找到处理后的气象数据CSV文件")
        print("   请先运行 extract_awos_weather.py 生成数据")
        return

    csv_path = csv_files[-1]  # 使用最新的文件

    print("=" * 80)
    print("📊 AWOS气象数据分析工具")
    print("=" * 80)
    print()
    print(f"📂 加载数据: {csv_path.name}")

    # 加载数据
    df = load_weather_data(csv_path)

    print(f"   ✅ 总计 {len(df)} 条记录")
    print(f"   ✅ {df['location_id'].nunique()} 个位置")
    print(f"   ✅ 时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

    # 检测数据质量问题
    print("\n🔍 检测数据质量...")
    issues = detect_data_quality_issues(df)
    if issues:
        for issue in issues:
            print(f"   {issue}")
    else:
        print("   ✅ 未发现明显数据质量问题")

    # 按位置分离数据
    split_by_location(df, processed_dir)

    # 生成报告
    print("\n📝 生成分析报告...")
    report = generate_summary_report(df)

    # 保存报告
    report_file = processed_dir / f"awos_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"   ✅ 报告已保存: {report_file.name}")

    # 打印报告摘要
    print("\n" + "=" * 80)
    print("📋 分析报告摘要")
    print("=" * 80)
    print(report[:2000])  # 打印前2000个字符
    print("...")
    print("\n完整报告请查看: " + report_file.name)
    print("=" * 80)


if __name__ == '__main__':
    main()
