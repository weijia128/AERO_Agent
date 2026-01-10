"""
航班信息查询工具

从 data 文件夹的日志文件中读取航班信息
支持多种航班号格式：中文名称（南航1234）、IATA代码（CZ1234）、ICAO代码（CSN1234）
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from tools.base import BaseTool
from config.airline_codes import normalize_flight_number, get_airline_name


def load_flight_data() -> Dict[str, Dict]:
    """从 data/raw 文件夹加载所有航班数据"""
    data_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    flights = {}

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return flights

    # 查找所有 Log_*.txt 文件（支持子目录）
    log_files = list(data_dir.glob("**/Log_*.txt"))

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # 解析日志行: [timestamp]{	json	}
                    try:
                        # 提取 JSON 部分
                        json_start = line.find('{')
                        if json_start == -1:
                            continue
                        json_str = line[json_start:]

                        # 修复 JSON 格式（移除多余逗号）
                        json_str = json_str.replace(',}', '}')
                        json_str = json_str.replace(',]', ']')

                        data = json.loads(json_str)
                        callsign = data.get("callsign", "")

                        if callsign:
                            # 转换为标准格式
                            flight_no = callsign.upper()
                            flights[flight_no] = {
                                "flight_no": flight_no,
                                "inorout": data.get("inorout", ""),  # A=到达, D=出发
                                "aldt": data.get("aldt", ""),  # 实际到达时间
                                "eldt": data.get("eldt", ""),  # 预计落地时间
                                "atot": data.get("atot", ""),  # 实际起飞时间
                                "etot": data.get("etot", ""),  # 预计起飞时间
                                "runway": data.get("runway", ""),
                                "stand": data.get("stand", ""),  # 停机位
                            }
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
            continue

    return flights


# 加载航班数据
_FLIGHT_DATA = None


def get_flight_data() -> Dict[str, Dict]:
    """获取航班数据（懒加载）"""
    global _FLIGHT_DATA
    if _FLIGHT_DATA is None:
        _FLIGHT_DATA = load_flight_data()
    return _FLIGHT_DATA


class GetAircraftInfoTool(BaseTool):
    """查询航班/机型信息"""

    name = "get_aircraft_info"
    description = """查询航班或飞机的详细信息。

输入参数:
- flight_no: 航班号（支持多种格式：南航1234/CZ1234/CSN1234）

返回信息:
- 航班号、航空公司、起降状态、时间、跑道、停机位等完整的航班计划信息"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        flight_no_raw = inputs.get("flight_no", "").strip()

        if not flight_no_raw:
            return {
                "observation": "请提供航班号",
            }

        # 保存原始输入格式（用于对话显示）
        flight_no_display = flight_no_raw

        # 将输入的航班号转换为ICAO格式（用于数据查询）
        flight_no_icao = normalize_flight_number(flight_no_raw)

        # 从 data 文件夹读取航班信息
        flight_data = get_flight_data()

        if flight_no_icao in flight_data:
            info = flight_data[flight_no_icao]

            # 解析航班类型
            inorout = "到达" if info.get("inorout") == "A" else "出发" if info.get("inorout") == "D" else "未知"

            # 提取时间信息
            time_info = []
            if info.get("inorout") == "A":  # 到达航班
                if info.get("aldt"):
                    time_info.append(f"实际落地: {info['aldt']}")
                if info.get("eldt"):
                    time_info.append(f"计划落地: {info['eldt']}")
            elif info.get("inorout") == "D":  # 出发航班
                if info.get("atot"):
                    time_info.append(f"实际起飞: {info['atot']}")
                if info.get("etot"):
                    time_info.append(f"计划起飞: {info['etot']}")

            time_str = ", ".join(time_info) if time_info else "无时间信息"

            # 获取航空公司名称
            airline_name = get_airline_name(flight_no_icao)

            # 构建观察结果
            observation = (
                f"【航班信息查询成功】\n"
                f"航班号: {info['flight_no']} ({airline_name})\n"
                f"航班类型: {inorout}\n"
                f"{time_str}\n"
                f"停机位: {info.get('stand', '未分配')}\n"
                f"跑道: {info.get('runway', '未分配')}"
            )

            return {
                "observation": observation,
                "incident": {
                    "flight_no": info["flight_no"],  # ICAO格式，用于内部处理
                    "flight_no_display": flight_no_display,  # 原始格式，用于对话显示
                    "airline": airline_name,
                    "stand": info.get("stand", ""),
                    "runway": info.get("runway", ""),
                    "flight_type": info.get("inorout", ""),
                    "scheduled_time": info.get("eldt") or info.get("etot", ""),
                    "actual_time": info.get("aldt") or info.get("atot", ""),
                },
            }
        else:
            # 尝试模糊匹配
            possible_matches = []
            search_prefix = flight_no_icao[:3] if len(flight_no_icao) >= 3 else ""

            if search_prefix:
                for fno in flight_data.keys():
                    if fno.startswith(search_prefix):
                        possible_matches.append(fno)

            # 返回未找到信息
            if possible_matches:
                matches_str = ", ".join(possible_matches[:5])
                obs = (
                    f"未找到航班: {flight_no_raw} (转换为: {flight_no_icao})\n"
                    f"可能的匹配航班: {matches_str}"
                )
            else:
                available = list(flight_data.keys())[:10]
                obs = (
                    f"未找到航班: {flight_no_raw} (转换为: {flight_no_icao})\n"
                    f"数据库中可用航班示例: {', '.join(available)}"
                )

            return {
                "observation": obs,
            }
