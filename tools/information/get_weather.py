"""
气象数据查询工具

从AWOS系统获取实时气象信息，包括温度、风速、气压、能见度等
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from tools.base import BaseTool


# 缓存气象数据
_WEATHER_DATA = None
_DATA_FILE = None


def load_weather_data() -> Optional[pd.DataFrame]:
    """从 data/processed 文件夹加载气象数据"""
    global _WEATHER_DATA, _DATA_FILE

    if _WEATHER_DATA is not None:
        return _WEATHER_DATA

    # 查找最新的气象数据CSV
    data_dir = Path(__file__).parent.parent.parent / "data" / "processed"

    if not data_dir.exists():
        return None

    # 查找最新的气象数据文件
    csv_files = list(data_dir.glob("awos_weather_*.csv"))

    if not csv_files:
        return None

    # 使用最新的文件
    latest_file = sorted(csv_files)[-1]
    _DATA_FILE = latest_file

    try:
        df = pd.read_csv(latest_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        _WEATHER_DATA = df
        return df
    except Exception as e:
        print(f"Error loading weather data: {e}")
        return None


def get_weather_data() -> Optional[pd.DataFrame]:
    """获取气象数据（懒加载）"""
    return load_weather_data()


def find_nearest_record(df: pd.DataFrame, location: str, timestamp: datetime) -> Optional[pd.Series]:
    """
    查找最接近指定时间和位置的气象记录

    Args:
        df: 气象数据框
        location: 位置ID
        timestamp: 目标时间

    Returns:
        最接近的记录，如果未找到返回None
    """
    # 筛选位置
    df_loc = df[df['location_id'] == location].copy()

    if len(df_loc) == 0:
        return None

    # 计算时间差
    df_loc['time_diff'] = (df_loc['timestamp'] - timestamp).abs()

    # 找到时间最接近的记录
    idx = df_loc['time_diff'].idxmin()
    nearest = df_loc.loc[idx]

    # 如果时间差超过1小时，认为数据不相关
    if nearest['time_diff'].total_seconds() > 3600:
        return None

    return nearest


def format_weather_info(record: pd.Series, location: str, timestamp: datetime = None) -> str:
    """格式化气象信息为可读文本"""
    if record is None or record.empty:
        return f"❌ 未找到位置 {location} 的气象数据"

    lines = []
    lines.append(f"【{location} 气象信息】")

    # 时间信息
    if timestamp:
        time_diff = (record['timestamp'] - timestamp).total_seconds()
        if time_diff < 60:
            time_str = f"{record['timestamp'].strftime('%H:%M:%S')}"
        else:
            time_str = f"{record['timestamp'].strftime('%H:%M:%S')} (相差 {abs(int(time_diff))} 秒)"
    else:
        time_str = record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

    lines.append(f"观测时间: {time_str}")

    # 温湿度信息
    if pd.notna(record.get('temperature')):
        lines.append(f"🌡️  温度: {record['temperature']:.1f}°C")
    if pd.notna(record.get('dew_point')):
        lines.append(f"💧 露点: {record['dew_point']:.1f}°C")
    if pd.notna(record.get('relative_humidity')):
        lines.append(f"💨 相对湿度: {record['relative_humidity']:.0f}%")

    # 风信息
    if pd.notna(record.get('wind_speed')):
        wind_dir_str = f"{record['wind_direction']:.0f}°" if pd.notna(record.get('wind_direction')) else "未知"
        lines.append(f"🌬️  风: {wind_dir_str} {record['wind_speed']:.1f} m/s")

        # 添加风速等级描述
        wind_speed = record['wind_speed']
        if wind_speed < 2:
            wind_desc = "微风"
        elif wind_speed < 5:
            wind_desc = "轻风"
        elif wind_speed < 8:
            wind_desc = "和风"
        elif wind_speed < 11:
            wind_desc = "清风"
        else:
            wind_desc = "强风"
        lines.append(f"   ({wind_desc})")

    # 气压信息
    if pd.notna(record.get('qnh')):
        lines.append(f"🔽 QNH: {record['qnh']:.0f} hPa")

    # 能见度信息
    if pd.notna(record.get('visibility')):
        vis_km = record['visibility'] / 1000
        lines.append(f"👁️  能见度: {vis_km:.1f} km")

    return "\n".join(lines)


class GetWeatherTool(BaseTool):
    """查询气象信息工具"""

    name = "get_weather"
    description = """查询机场特定位置的实时气象信息。

输入参数:
- location: 位置ID（必需），可选值：
  * 跑道端: 05L, 05R, 06L, 06R, 23L, 23R, 24L, 24R
  * 区域: NORTH, SOUTH
  * 或使用 "推荐" 自动选择最佳观测点

- timestamp: 时间戳（可选），格式: "YYYY-MM-DD HH:MM:SS"
  如果不指定，返回最新的可用数据

返回信息:
- 温度、露点、相对湿度
- 风向、风速
- 气压（QNH）
- 能见度（RVR）
- 数据观测时间

使用场景:
- 评估气象条件对应急处置的影响
- 判断是否需要调整应急响应策略
- 分析天气因素对航班运行的影响"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        location = inputs.get("location", "").strip()
        timestamp_str = inputs.get("timestamp", "").strip()

        if not location:
            return {
                "observation": "请提供位置参数（location），例如: 05L, NORTH, 推荐"
            }

        # 加载气象数据
        df = get_weather_data()

        if df is None or len(df) == 0:
            return {
                "observation": "❌ 气象数据不可用，请确保已运行 extract_awos_weather.py 生成数据"
            }

        # 处理"推荐"位置
        if location == "推荐" or location.lower() in ["推荐", "recommend", "auto"]:
            # 根据事件位置自动选择观测点
            incident_position = state.get("incident", {}).get("position", "")

            if not incident_position:
                return {
                    "observation": "❌ 无法自动选择观测点：未提供事件位置信息"
                }

            # 映射规则：根据事件位置选择最近的观测点
            position_to_sensor = {
                # 05号跑道一端 -> 05L
                "501": "05L",
                # 06号跑道一端 -> 06L
                "601": "06L",
                # 其他情况默认用NORTH
            }

            location = position_to_sensor.get(incident_position, "NORTH")

        # 解析时间参数
        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return {
                    "observation": f"❌ 时间格式错误: {timestamp_str}，请使用格式: YYYY-MM-DD HH:MM:%S"
                }
        else:
            # 不指定时间时，使用数据的最新时间
            timestamp = df['timestamp'].max()

        # 查找气象记录
        record = find_nearest_record(df, location, timestamp)

        if record is None:
            # 位置不存在
            available_locations = ", ".join(sorted(df['location_id'].unique()))
            return {
                "observation": f"❌ 未找到位置 '{location}' 的气象数据\n"
                             f"可用的位置: {available_locations}\n"
                             f"或者使用 location='推荐' 自动选择观测点"
            }

        # 格式化输出
        observation = format_weather_info(record, location, timestamp)

        # 构建返回结果
        result = {
            "observation": observation,
            "weather": {
                "location": location,
                "timestamp": record['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                "temperature": float(record['temperature']) if pd.notna(record.get('temperature')) else None,
                "dew_point": float(record['dew_point']) if pd.notna(record.get('dew_point')) else None,
                "relative_humidity": float(record['relative_humidity']) if pd.notna(record.get('relative_humidity')) else None,
                "wind_direction": float(record['wind_direction']) if pd.notna(record.get('wind_direction')) else None,
                "wind_speed": float(record['wind_speed']) if pd.notna(record.get('wind_speed')) else None,
                "qnh": float(record['qnh']) if pd.notna(record.get('qnh')) else None,
                "visibility": float(record['visibility']) if pd.notna(record.get('visibility')) else None,
            }
        }

        # 如果有10米风速数据，也包含进来
        if pd.notna(record.get('wind_speed_10m')):
            result['weather']['wind_speed_10m'] = float(record['wind_speed_10m'])

        return result
