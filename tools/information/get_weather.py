"""
气象数据查询工具

从AWOS系统获取实时气象信息，包括温度、风速、气压、能见度等
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re
from tools.base import BaseTool


# 缓存气象数据
_WEATHER_DATA = None
_DATA_FILE = None
_RAW_WEATHER_STATS = None


def _load_raw_weather_stats() -> Optional[Dict[str, Dict[str, float]]]:
    """从原始AWOS日志中提取基础统计（均值）"""
    global _RAW_WEATHER_STATS
    if _RAW_WEATHER_STATS is not None:
        return _RAW_WEATHER_STATS

    raw_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "气象数据"
    if not raw_dir.exists():
        _RAW_WEATHER_STATS = None
        return None

    stats: Dict[str, Dict[str, float]] = {}
    counts: Dict[str, Dict[str, int]] = {}
    max_lines = 20000
    lines_read = 0

    for file_path in sorted(raw_dir.glob("AWOS_*.log")):
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if lines_read >= max_lines:
                        break
                    idx = line.find("{")
                    if idx == -1:
                        continue
                    try:
                        payload = line[idx:].strip()
                        record = json.loads(payload)
                    except Exception:
                        continue

                    header = record.get("header", {})
                    data = record.get("data", {})
                    location = header.get("locationId")
                    message_type = header.get("messageType")
                    if not location or not message_type:
                        continue

                    location = str(location).upper()
                    stats.setdefault(location, {})
                    counts.setdefault(location, {})

                    def _accumulate(key: str, value: Optional[float]) -> None:
                        if value is None:
                            return
                        stats[location][key] = stats[location].get(key, 0.0) + float(value)
                        counts[location][key] = counts[location].get(key, 0) + 1

                    if message_type == "HUMITEMP":
                        _accumulate("temperature", data.get("tains") or data.get("ta10m"))
                        _accumulate("dew_point", data.get("tdins"))
                        _accumulate("relative_humidity", data.get("rhins"))
                    elif message_type == "WIND":
                        _accumulate("wind_direction", data.get("wdins") or data.get("wd10m"))
                        _accumulate("wind_speed", data.get("wsins") or data.get("ws10m"))
                    elif message_type == "PRESS":
                        _accumulate("qnh", data.get("qnhins"))
                    elif message_type == "VIS":
                        _accumulate("visibility", data.get("vis") or data.get("vis10m"))

                    lines_read += 1
            if lines_read >= max_lines:
                break
        except Exception:
            continue

    if not stats:
        _RAW_WEATHER_STATS = None
        return None

    averaged: Dict[str, Dict[str, float]] = {}
    for location, values in stats.items():
        averaged[location] = {}
        for key, total in values.items():
            count = counts.get(location, {}).get(key, 0)
            if count:
                averaged[location][key] = total / count

    _RAW_WEATHER_STATS = averaged
    return averaged


def _build_simulated_weather_data(
    base_time: datetime,
    raw_stats: Optional[Dict[str, Dict[str, float]]] = None,
) -> pd.DataFrame:
    """构建模拟气象数据（参考原始AWOS统计）"""
    locations = ["05L", "05R", "06L", "06R", "23L", "23R", "24L", "24R", "NORTH", "SOUTH"]
    if raw_stats:
        for loc in raw_stats.keys():
            if loc not in locations:
                locations.append(loc)
    records = []
    for loc in locations:
        seed = sum(ord(ch) for ch in loc)
        stats = raw_stats.get(loc, {}) if raw_stats else {}
        temp = stats.get("temperature", 18.0) + ((seed % 5) - 2) * 0.3
        dew_point = stats.get("dew_point", temp - 4.0)
        rh = stats.get("relative_humidity", 55.0) + ((seed % 7) - 3)
        wind_dir = stats.get("wind_direction", 260.0) + (seed % 12)
        wind_speed = stats.get("wind_speed", 3.0) + (seed % 5) * 0.3
        wind_speed_10m = wind_speed + 0.5
        qnh = stats.get("qnh", 1012.0) + ((seed % 5) - 2) * 0.2
        visibility = stats.get("visibility", 10000.0) - (seed % 4) * 300.0

        for offset in (-30, 0, 30):
            ts = base_time + timedelta(minutes=offset)
            records.append({
                "location_id": loc,
                "timestamp": ts,
                "temperature": temp,
                "dew_point": dew_point,
                "relative_humidity": rh,
                "wind_direction": wind_dir,
                "wind_speed": wind_speed,
                "wind_speed_10m": wind_speed_10m,
                "qnh": qnh,
                "visibility": visibility,
            })

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


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


def normalize_location(location: str) -> str:
    """规范化位置输入为观测点编号"""
    if not location:
        return ""
    loc = location.strip().upper()
    # 兼容 "跑道27L"/"RWY27L"/"RUNWAY27L"
    loc = re.sub(r"^(RUNWAY|RWY|跑道)\s*", "", loc)
    return loc


def find_nearest_record(
    df: pd.DataFrame,
    location: str,
    timestamp: Optional[datetime],
) -> Optional[pd.Series]:
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
    if timestamp is None:
        timestamp = df_loc['timestamp'].max()
    df_loc['time_diff'] = (df_loc['timestamp'] - timestamp).abs()

    # 找到时间最接近的记录
    idx = df_loc['time_diff'].idxmin()
    nearest = df_loc.loc[idx]

    # 如果时间差超过1小时，认为数据不相关
    if nearest['time_diff'].total_seconds() > 3600:
        return None

    return nearest


def _is_runway_location(location: str) -> bool:
    return bool(re.fullmatch(r"\d{2}[LRC]?", location))


def _runway_number(location: str) -> Optional[int]:
    match = re.fullmatch(r"(\d{2})[LRC]?", location)
    if not match:
        return None
    return int(match.group(1))


def _runway_side(location: str) -> Optional[str]:
    match = re.fullmatch(r"\d{2}([LRC])", location)
    if not match:
        return None
    return match.group(1)


def _find_fallback_record(
    df: pd.DataFrame,
    requested_location: str,
    timestamp: Optional[datetime],
) -> tuple[Optional[str], Optional[pd.Series]]:
    available = sorted(df["location_id"].dropna().unique().tolist())
    if not available:
        return None, None

    ordered_candidates: list[str] = []
    if _is_runway_location(requested_location):
        req_num = _runway_number(requested_location)
        req_side = _runway_side(requested_location)
        runway_candidates = [loc for loc in available if _is_runway_location(loc)]
        if req_num is not None and runway_candidates:
            runway_candidates.sort(
                key=lambda loc: (
                    abs((_runway_number(loc) or 0) - req_num),
                    0 if req_side and _runway_side(loc) == req_side else 1,
                    loc,
                )
            )
            ordered_candidates.extend(runway_candidates)
    else:
        for pref in ["NORTH", "SOUTH"]:
            if pref in available:
                ordered_candidates.append(pref)

    for loc in available:
        if loc not in ordered_candidates:
            ordered_candidates.append(loc)

    for loc in ordered_candidates:
        record = find_nearest_record(df, loc, timestamp)
        if record is not None:
            return loc, record

    return None, None


def format_weather_info(
    record: pd.Series,
    location: str,
    timestamp: Optional[datetime] = None,
) -> str:
    """格式化气象信息为可读文本"""
    if record is None or record.empty:
        return f"❌ 未找到位置 {location} 的气象数据"

    lines = []
    lines.append(f"【{location} 气象信息】")

    # 时间信息
    if timestamp is not None:
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
        using_simulated = False

        if df is None or len(df) == 0:
            # 使用模拟气象数据（10月21日）
            base_time = None
            if timestamp_str:
                try:
                    base_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    base_time = None
            if base_time is None:
                incident = state.get("incident", {})
                incident_time = incident.get("incident_time") or incident.get("start_time")
                if incident_time:
                    try:
                        base_time = datetime.fromisoformat(incident_time)
                    except (ValueError, TypeError):
                        base_time = None
            if base_time is None:
                base_time = datetime.fromisoformat("2025-10-21 10:00:00")
            raw_stats = _load_raw_weather_stats()
            df = _build_simulated_weather_data(base_time, raw_stats)
            _WEATHER_DATA = df
            using_simulated = True

        # 处理"推荐"位置
        requested_location = location
        if location == "推荐" or location.lower() in ["推荐", "recommend", "auto"]:
            incident_position = state.get("incident", {}).get("position", "")
            if not incident_position:
                return {
                    "observation": "❌ 无法自动选择观测点：未提供事件位置信息"
                }
            location = incident_position
            requested_location = incident_position

        location = normalize_location(location)
        requested_location = normalize_location(requested_location)

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

        fallback_note = ""
        if record is None:
            fallback_location, fallback_record = _find_fallback_record(df, location, timestamp)
            if fallback_record is None:
                available_locations = ", ".join(sorted(df['location_id'].unique()))
                return {
                    "observation": f"❌ 未找到位置 '{location}' 的气象数据\n"
                                 f"可用的位置: {available_locations}\n"
                                 f"或者使用 location='推荐' 自动选择观测点"
                }
            record = fallback_record
            fallback_note = f"⚠️ 位置 {location} 无气象数据，改用就近观测点 {fallback_location}\n"
            location = fallback_location

        # 格式化输出
        observation = fallback_note + format_weather_info(record, location, timestamp)
        if using_simulated:
            observation = "⚠️ 使用模拟气象数据（参考原始AWOS日志）\n" + observation

        # 构建返回结果
        result: Dict[str, Any] = {
            "observation": observation,
            "weather": {
                "location": location,
                **({"requested_location": requested_location} if requested_location else {}),
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
