"""
航班计划查询工具（仅用于展示，不影响对话状态）
"""
import json
from pathlib import Path
from typing import Dict, Any, List

from tools.base import BaseTool
from config.airline_codes import normalize_flight_number


def _parse_log_line(line: str) -> Dict[str, Any]:
    json_start = line.find("{")
    if json_start == -1:
        return {}
    json_str = line[json_start:].strip()
    json_str = json_str.replace(",}", "}").replace(",]", "]")
    try:
        return json.loads(json_str)
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
    """从 Log_4.txt 查询航班计划并返回表格文本"""

    name = "flight_plan_lookup"
    description = """从 data/raw/航班计划/Log_4.txt 查询航班计划（仅展示）。

输入参数:
- flight_no: 航班号（支持多种格式）

返回信息:
- 航班计划表（不会更新对话状态）"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        flight_no_raw = inputs.get("flight_no", "").strip()
        if not flight_no_raw:
            return {"observation": "缺少航班号，未查询航班计划"}

        flight_no = normalize_flight_number(flight_no_raw)
        plan_file = Path(__file__).resolve().parents[2] / "data" / "raw" / "航班计划" / "Log_4.txt"
        if not plan_file.exists():
            return {"observation": f"未找到航班计划文件: {plan_file}"}

        records: List[Dict[str, Any]] = []
        with plan_file.open("r", encoding="utf-8") as f:
            for line in f:
                data = _parse_log_line(line)
                if not data:
                    continue
                if data.get("callsign", "").upper() == flight_no.upper():
                    records.append(data)

        if not records:
            return {
                "observation": f"Log_4 中未找到航班 {flight_no} 的计划记录",
            }

        table = _format_plan_table(records)
        # 提取简要信息用于 observation
        rec = records[0]
        inorout = "出发" if rec.get("inorout") == "D" else "到达" if rec.get("inorout") == "A" else rec.get("inorout", "")
        stand = rec.get("stand", "N/A")
        runway = rec.get("runway", "N/A")
        brief = f"已查到航班计划: {flight_no} {inorout}, 机位 {stand}, 跑道 {runway}"

        return {
            "observation": brief,
            "flight_plan_table": table,
        }
