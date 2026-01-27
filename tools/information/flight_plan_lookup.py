"""
航班计划查询工具（仅用于展示，不影响对话状态）
"""
import json
from pathlib import Path
from typing import Dict, Any, List, cast

from tools.base import BaseTool
from config.airline_codes import normalize_flight_number


def _parse_log_line(line: str) -> Dict[str, Any]:
    json_start = line.find("{")
    if json_start == -1:
        return {}
    json_str = line[json_start:].strip()
    json_str = json_str.replace(",}", "}").replace(",]", "]")
    try:
        return cast(Dict[str, Any], json.loads(json_str))
    except json.JSONDecodeError:
        return {}


def _format_plan_table(records: List[Dict[str, Any]]) -> str:
    headers = ["callsign", "inorout", "stand", "runway", "eldt", "etot", "aldt", "atot"]
    lines = [" | ".join(headers)]
    lines.append(" | ".join(["-" * len(h) for h in headers]))
    for rec in records:
        row = [str(rec.get(h, "")) for h in headers]
        lines.append(" | ".join(row))
    return "\n".join(lines)


class FlightPlanLookupTool(BaseTool):
    """从航班计划数据查询航班并返回表格文本"""

    name = "flight_plan_lookup"
    description = """从航班计划数据查询航班（仅展示）。

输入参数:
- flight_no: 航班号（支持多种格式）

返回信息:
- 航班计划表（不会更新对话状态）"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        flight_no_raw = inputs.get("flight_no", "").strip()
        if not flight_no_raw:
            return {"observation": "缺少航班号，未查询航班计划"}

        flight_no = normalize_flight_number(flight_no_raw)

        # 优先使用天府机场 10/21 数据
        preferred_dir = Path(__file__).resolve().parents[2] / "data" / "raw" / "天府机场数据" / "航班计划-10月21"
        plan_files: List[Path] = []
        if preferred_dir.exists():
            plan_files = sorted(preferred_dir.glob("Log_*.txt"))
        else:
            return {"observation": f"未找到航班计划文件: {preferred_dir}"}

        if not plan_files:
            return {"observation": "未找到可用的航班计划文件"}

        records: List[Dict[str, Any]] = []
        for plan_file in plan_files:
            with plan_file.open("r", encoding="utf-8") as f:
                for line in f:
                    data = _parse_log_line(line)
                    if not data:
                        continue
                    if data.get("callsign", "").upper() == flight_no.upper():
                        data["_source_file"] = plan_file.name
                        records.append(data)

        if not records:
            return {
                "observation": f"未找到航班 {flight_no} 的计划记录",
            }

        table = _format_plan_table(records)
        # 提取简要信息用于 observation
        rec = records[0]
        inorout = "出发" if rec.get("inorout") == "D" else "到达" if rec.get("inorout") == "A" else rec.get("inorout", "")
        stand = rec.get("stand", "N/A")
        runway = rec.get("runway", "N/A")

        # 提取时间信息
        eldt = rec.get("eldt") or rec.get("aldt")  # 预计降落时间/实际降落时间
        etot = rec.get("etot") or rec.get("atot")  # 预计起飞时间/实际起飞时间

        # 确定参考时间（优先使用起飞时间，如果没有则用降落时间）
        reference_time = etot or eldt

        # 将查询到的航班信息写入 state
        if "reference_flight" not in state:
            state["reference_flight"] = {}

        state["reference_flight"] = {
            "callsign": flight_no,
            "inorout": rec.get("inorout"),
            "stand": stand,
            "runway": runway,
            "eldt": eldt,
            "etot": etot,
            "reference_time": reference_time,  # 用于时间窗口计算的基准时间
        }

        # 构建简要说明（包含时间信息）
        time_info = ""
        if etot:
            time_info = f", 计划起飞 {etot}"
        elif eldt:
            time_info = f", 计划降落 {eldt}"

        source_file = rec.get("_source_file", "")
        source_note = f" (来源: {source_file})" if source_file else ""
        brief = f"已查到航班计划: {flight_no} {inorout}, 机位 {stand}, 跑道 {runway}{time_info}{source_note}"

        return {
            "observation": brief,
            "flight_plan_table": table,
            "reference_flight": state["reference_flight"],  # 返回给调用者
        }
