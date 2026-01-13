#!/usr/bin/env python3
"""
AWOS气象数据清洗和导出工具

提供数据清洗功能（填充缺失值、平滑处理等），
并将数据导出为Excel格式（带多个工作表）。

使用方法:
    python scripts/data_processing/export_awos_to_excel.py

输出:
    data/processed/awos_weather_<date>.xlsx
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Literal


def load_weather_data(csv_path: Path) -> pd.DataFrame:
    """加载气象数据CSV"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(['timestamp', 'location_id']).reset_index(drop=True)
    return df


def clean_temperature(df: pd.DataFrame, method: Literal['drop', 'ffill', 'interpolate'] = 'interpolate') -> pd.DataFrame:
    """
    清洗温度数据

    Args:
        df: 数据框
        method: 清洗方法
            - 'drop': 删除包含温度缺失值的行
            - 'ffill': 前向填充
            - 'interpolate': 线性插值（默认）
    """
    df_clean = df.copy()

    if method == 'drop':
        df_clean = df_clean.dropna(subset=['temperature'])
    elif method == 'ffill':
        # 按位置分组前向填充
        df_clean['temperature'] = df_clean.groupby('location_id')['temperature'].fillna(method='ffill')
    elif method == 'interpolate':
        # 按位置分组线性插值
        df_clean['temperature'] = df_clean.groupby('location_id')['temperature'].transform(
            lambda x: x.interpolate(method='linear', limit_direction='both')
        )

    # 同样处理露点和湿度
    if method == 'drop':
        df_clean = df_clean.dropna(subset=['dew_point', 'relative_humidity'])
    elif method == 'ffill':
        df_clean['dew_point'] = df_clean.groupby('location_id')['dew_point'].fillna(method='ffill')
        df_clean['relative_humidity'] = df_clean.groupby('location_id')['relative_humidity'].fillna(method='ffill')
    elif method == 'interpolate':
        df_clean['dew_point'] = df_clean.groupby('location_id')['dew_point'].transform(
            lambda x: x.interpolate(method='linear', limit_direction='both')
        )
        df_clean['relative_humidity'] = df_clean.groupby('location_id')['relative_humidity'].transform(
            lambda x: x.interpolate(method='linear', limit_direction='both')
        )

    return df_clean


def clean_wind(df: pd.DataFrame, method: Literal['drop', 'ffill', 'interpolate'] = 'interpolate') -> pd.DataFrame:
    """
    清洗风数据

    Args:
        df: 数据框
        method: 清洗方法
    """
    df_clean = df.copy()

    wind_fields = ['wind_direction', 'wind_speed', 'wind_direction_10m', 'wind_speed_10m',
                   'wind_direction_2m', 'wind_speed_2m', 'cross_wind_2a', 'head_wind_2a']

    if method == 'drop':
        df_clean = df_clean.dropna(subset=['wind_speed'])
    elif method == 'ffill':
        for field in wind_fields:
            df_clean[field] = df_clean.groupby('location_id')[field].fillna(method='ffill')
    elif method == 'interpolate':
        for field in wind_fields:
            df_clean[field] = df_clean.groupby('location_id')[field].transform(
                lambda x: x.interpolate(method='linear', limit_direction='both')
            )

    return df_clean


def clean_pressure(df: pd.DataFrame, method: Literal['drop', 'ffill', 'interpolate'] = 'interpolate') -> pd.DataFrame:
    """
    清洗气压数据

    Args:
        df: 数据框
        method: 清洗方法
    """
    df_clean = df.copy()

    pressure_fields = ['qnh', 'qfe', 'station_pressure']

    if method == 'drop':
        df_clean = df_clean.dropna(subset=['qnh'])
    elif method == 'ffill':
        for field in pressure_fields:
            df_clean[field] = df_clean.groupby('location_id')[field].fillna(method='ffill')
    elif method == 'interpolate':
        for field in pressure_fields:
            df_clean[field] = df_clean.groupby('location_id')[field].transform(
                lambda x: x.interpolate(method='linear', limit_direction='both')
            )

    return df_clean


def clean_visibility(df: pd.DataFrame, method: Literal['drop', 'ffill', 'interpolate'] = 'interpolate') -> pd.DataFrame:
    """
    清洗能见度数据

    Args:
        df: 数据框
        method: 清洗方法
    """
    df_clean = df.copy()

    vis_fields = ['visibility', 'rvr']

    if method == 'drop':
        df_clean = df_clean.dropna(subset=['visibility'])
    elif method == 'ffill':
        for field in vis_fields:
            df_clean[field] = df_clean.groupby('location_id')[field].fillna(method='ffill')
    elif method == 'interpolate':
        for field in vis_fields:
            df_clean[field] = df_clean.groupby('location_id')[field].transform(
                lambda x: x.interpolate(method='linear', limit_direction='both')
            )

    return df_clean


def clean_all(df: pd.DataFrame, method: Literal['drop', 'ffill', 'interpolate'] = 'interpolate') -> pd.DataFrame:
    """
    清洗所有字段

    Args:
        df: 数据框
        method: 清洗方法
    """
    df_clean = df.copy()

    # 清洗各类数据
    df_clean = clean_temperature(df_clean, method)
    df_clean = clean_wind(df_clean, method)
    df_clean = clean_pressure(df_clean, method)
    df_clean = clean_visibility(df_clean, method)

    return df_clean


def export_to_excel(df: pd.DataFrame, df_clean: Optional[pd.DataFrame], output_path: Path) -> None:
    """
    导出数据到Excel（多个工作表）

    Args:
        df: 原始数据
        df_clean: 清洗后的数据
        output_path: 输出Excel文件路径
    """
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # 工作表1: 原始数据
        df.to_excel(writer, sheet_name='原始数据', index=False)

        # 工作表2: 清洗后数据
        if df_clean is not None:
            df_clean.to_excel(writer, sheet_name='清洗后数据', index=False)

        # 工作表3: 按位置分组统计
        location_stats = []
        for location_id in sorted(df['location_id'].unique()):
            df_loc = df[df['location_id'] == location_id]
            stats = {
                '位置': location_id,
                '记录数': len(df_loc),
                '温度记录数': df_loc['temperature'].notna().sum(),
                '平均温度(°C)': df_loc['temperature'].mean() if df_loc['temperature'].notna().any() else None,
                '风速记录数': df_loc['wind_speed'].notna().sum(),
                '平均风速(m/s)': df_loc['wind_speed'].mean() if df_loc['wind_speed'].notna().any() else None,
                'QNH记录数': df_loc['qnh'].notna().sum(),
                '平均QNH(hPa)': df_loc['qnh'].mean() if df_loc['qnh'].notna().any() else None,
            }
            location_stats.append(stats)

        pd.DataFrame(location_stats).to_excel(writer, sheet_name='位置统计', index=False)

        # 工作表4: 数据质量报告
        quality_report = []
        for field in df.columns:
            if field not in ['timestamp', 'location_id']:
                non_null_count = df[field].notna().sum()
                null_count = df[field].isna().sum()
                quality_report.append({
                    '字段': field,
                    '有效记录数': non_null_count,
                    '缺失记录数': null_count,
                    '完整率(%)': (non_null_count / len(df)) * 100 if len(df) > 0 else 0,
                })

        pd.DataFrame(quality_report).to_excel(writer, sheet_name='数据质量', index=False)

        # 工作表5: 小时平均值（用于趋势分析）
        df['hour'] = df['timestamp'].dt.floor('H')
        hourly_avg = df.groupby(['hour', 'location_id']).agg({
            'temperature': 'mean',
            'wind_speed': 'mean',
            'wind_direction': 'mean',
            'relative_humidity': 'mean',
            'qnh': 'mean',
            'visibility': 'mean',
        }).reset_index()
        hourly_avg.columns = ['时间', '位置', '平均温度(°C)', '平均风速(m/s)', '平均风向(度)',
                              '平均湿度(%)', '平均QNH(hPa)', '平均能见度(m)']
        hourly_avg.to_excel(writer, sheet_name='小时平均值', index=False)


def main():
    """主函数"""
    base_dir = Path(__file__).parent.parent.parent
    processed_dir = base_dir / 'data' / 'processed'

    print("=" * 80)
    print("🧹 AWOS气象数据清洗和导出工具")
    print("=" * 80)
    print()

    # 查找最新的气象数据CSV
    csv_files = sorted(processed_dir.glob('awos_weather_*.csv'))
    if not csv_files:
        print("❌ 未找到处理后的气象数据CSV文件")
        print("   请先运行 extract_awos_weather.py 生成数据")
        return

    csv_path = csv_files[-1]
    print(f"📂 加载数据: {csv_path.name}")

    # 加载数据
    df = load_weather_data(csv_path)
    print(f"   ✅ 总计 {len(df)} 条记录")
    print()

    # 选择清洗方法
    print("请选择数据清洗方法:")
    print("  1. 不清洗（使用原始数据）")
    print("  2. 删除缺失值（drop）")
    print("  3. 前向填充（ffill）")
    print("  4. 线性插值（interpolate，推荐）")

    # 默认使用插值
    choice = '4'
    print(f"\n使用方法: 线性插值 (interpolate)")

    method_map = {
        '1': None,
        '2': 'drop',
        '3': 'ffill',
        '4': 'interpolate',
    }
    method = method_map.get(choice)

    # 执行清洗
    if method is None:
        df_clean = None
        print("⏭️  跳过数据清洗")
    else:
        print(f"\n⏳ 正在清洗数据... (方法: {method})")
        df_clean = clean_all(df, method=method)

        # 统计清洗效果
        original_missing = df.isna().sum().sum()
        cleaned_missing = df_clean.isna().sum().sum()
        filled = original_missing - cleaned_missing

        print(f"   ✅ 清洗完成")
        print(f"   填充缺失值: {filled} 个")
        print(f"   剩余缺失值: {cleaned_missing} 个")

    # 导出到Excel
    print("\n💾 导出到Excel...")
    output_file = processed_dir / f"awos_weather_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    export_to_excel(df, df_clean, output_file)

    print(f"   ✅ 已保存: {output_file.name}")
    print()
    print("=" * 80)
    print("✅ 导出完成！")
    print(f"📊 Excel文件包含 5 个工作表:")
    print(f"   1. 原始数据")
    if df_clean is not None:
        print(f"   2. 清洗后数据")
    else:
        print(f"   2. (跳过清洗)")
    print(f"   3. 位置统计")
    print(f"   4. 数据质量")
    print(f"   5. 小时平均值")
    print("=" * 80)


if __name__ == '__main__':
    main()
