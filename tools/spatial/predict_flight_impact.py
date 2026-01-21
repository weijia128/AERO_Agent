"""
航班影响预测工具

基于历史航班计划数据 + 拓扑图分析，预测泄漏事件对航班运行的影响
"""
import logging
import os
import sys
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 添加父目录到路径以便导入 scripts/data_processing 模块
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(project_root, "scripts"))

try:
    from data_processing.parse_flight_plan import FlightPlanParser, filter_by_time_range
except ModuleNotFoundError:
    # 尝试直接导入
    try:
        from parse_flight_plan import FlightPlanParser, filter_by_time_range
    except ModuleNotFoundError:
        # 创建临时占位符
        FlightPlanParser = None
        filter_by_time_range = None

from tools.base import BaseTool
from tools.spatial.topology_loader import get_topology_loader


# 延误估算规则（分钟）
DELAY_RULES = {
    "stand_blocked": {
        "departure": 30,  # 机位被封锁，出港延误30分钟
        "arrival": 45,    # 进港航班需改机位，延误45分钟
    },
    "taxiway_blocked": {
        "departure": 15,  # 滑行道封锁，绕行延误15分钟
        "arrival": 20,    # 进港绕行延误20分钟
    },
    "runway_blocked": {
        "departure": 60,  # 跑道封锁，重大延误60分钟
        "arrival": 60,    # 进港航班重大延误60分钟
    },
}


class PredictFlightImpactTool(BaseTool):
    """预测航班影响工具"""

    name = "predict_flight_impact"
    description = """基于历史航班数据和拓扑图，预测泄漏事件对航班运行的影响。

输入参数:
- time_window: 预测时间窗口（小时），默认2小时
- flight_plan_file: 航班计划文件路径（可选）
- use_cache: 是否使用缓存的航班数据

返回信息:
- 受影响航班列表
- 估计延误时间
- 受影响航班统计"""

    def __init__(self):
        super().__init__()
        self._flight_data_cache = None
        self._cache_file = None

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 检查是否有空间分析结果
        spatial_analysis = state.get("spatial_analysis", {})
        if not spatial_analysis:
            return {"observation": "需要先执行 calculate_impact_zone 工具获取影响范围"}

        # 获取参数
        time_window_hours = inputs.get("time_window", 2)
        flight_plan_file = inputs.get("flight_plan_file")
        use_cache = inputs.get("use_cache", True)

        # 获取受影响节点
        affected_stands = spatial_analysis.get("affected_stands", [])
        affected_runways = spatial_analysis.get("affected_runways", [])
        affected_taxiways = spatial_analysis.get("affected_taxiways", [])

        if not (affected_stands or affected_runways or affected_taxiways):
            return {"observation": "影响范围分析显示无节点受影响"}

        # 加载航班数据
        try:
            flight_data = self._load_flight_data(flight_plan_file, use_cache)
        except Exception as e:
            return {
                "observation": f"无法加载航班数据: {str(e)}\n"
                               f"请确保已生成航班计划数据文件"
            }

        if not flight_data:
            return {"observation": "未找到航班数据"}

        # 获取时间窗口的起点时间（优先级：参考航班时间 > 事故时间 > 默认时间）
        incident = state.get("incident", {})
        reference_flight = state.get("reference_flight", {})

        current_time = None

        # 第1优先级：从参考航班中获取时间（用户提供的航班号）
        if reference_flight:
            reference_time = reference_flight.get("reference_time")
            if reference_time:
                try:
                    current_time = datetime.fromisoformat(reference_time)
                except (ValueError, TypeError):
                    pass

        # 第2优先级：从 incident 中获取时间
        if current_time is None:
            incident_time = incident.get("incident_time") or incident.get("start_time")
            if incident_time:
                try:
                    current_time = datetime.fromisoformat(incident_time)
                except (ValueError, TypeError):
                    pass

        # 第3优先级：使用默认时间（匹配航班数据集）
        if current_time is None:
            current_time = datetime.fromisoformat("2026-01-06 10:00:00")
            time_source = "default_time"
        else:
            time_source = None

        if reference_flight and reference_flight.get("reference_time"):
            time_source = "reference_flight"
        elif incident.get("incident_time") or incident.get("start_time"):
            time_source = "incident_time"
        if time_source is None:
            time_source = "default_time"

        # 预测时间窗口
        end_time = current_time + timedelta(hours=time_window_hours)

        # 筛选时间窗口内的航班
        relevant_flights = self._filter_flights_by_time(
            flight_data,
            current_time,
            end_time
        )

        # 匹配受影响航班
        affected_flights = self._match_affected_flights(
            relevant_flights,
            affected_stands,
            affected_runways,
            affected_taxiways
        )

        # 计算延误
        impact_details = self._calculate_delays(affected_flights)

        # 生成观测结果
        observation = self._generate_observation(
            impact_details,
            time_window_hours,
            current_time,
            end_time
        )

        observation = f"{observation}\n预测基准时间: {current_time.isoformat()} (source={time_source})"

        return {
            "observation": observation,
            "flight_impact": {
                "time_window": {
                    "start": current_time.isoformat(),
                    "end": end_time.isoformat(),
                    "hours": time_window_hours
                },
                "affected_flights": impact_details["flights"],
                "statistics": impact_details["statistics"],
                "affected_nodes": {
                    "stands": affected_stands,
                    "runways": affected_runways,
                    "taxiways": affected_taxiways
                }
            }
        }

    def _load_flight_data(
        self,
        flight_plan_file: Optional[str],
        use_cache: bool
    ) -> List[Dict[str, Any]]:
        """加载航班计划数据"""
        # 如果有缓存且允许使用，直接返回
        if use_cache and self._flight_data_cache is not None:
            if flight_plan_file is None or flight_plan_file == self._cache_file:
                return self._flight_data_cache

        # 确定文件路径
        if flight_plan_file is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(project_root, "data", "raw", "航班计划")
            # 优先使用真实数据集（2026-01-06 8-12点）
            primary_file = os.path.join(data_dir, "Flight_Plan_2026-01-06_08-12.txt")
            fallback_file = os.path.join(data_dir, "Log_1.txt")

            if os.path.exists(primary_file):
                flight_plan_file = primary_file
            elif os.path.exists(fallback_file):
                flight_plan_file = fallback_file
            else:
                raise FileNotFoundError(f"未找到航班计划文件: {primary_file} 或 {fallback_file}")

        if not os.path.exists(flight_plan_file):
            raise FileNotFoundError(f"航班计划文件不存在: {flight_plan_file}")

        # 解析文件
        if FlightPlanParser is None:
            raise ImportError("FlightPlanParser 模块未正确导入")

        parser = FlightPlanParser()
        flight_data = parser.parse_file(flight_plan_file)

        # 缓存数据
        self._flight_data_cache = flight_data
        self._cache_file = flight_plan_file

        return flight_data

    def _filter_flights_by_time(
        self,
        flight_data: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """筛选时间窗口内的航班"""
        relevant = []

        for flight in flight_data:
            # 检查起飞时间或降落时间是否在窗口内
            # 注意：字段名是小写的
            etot = flight.get('etot') or flight.get('atot')
            eldt = flight.get('eldt') or flight.get('aldt')

            flight_in_window = False

            if etot:
                try:
                    etot_dt = datetime.fromisoformat(etot)
                    if start_time <= etot_dt <= end_time:
                        flight_in_window = True
                except (ValueError, TypeError) as e:
                    logger.debug(f"解析航班起飞时间失败 etot={etot}: {e}")

            if eldt:
                try:
                    eldt_dt = datetime.fromisoformat(eldt)
                    if start_time <= eldt_dt <= end_time:
                        flight_in_window = True
                except (ValueError, TypeError) as e:
                    logger.debug(f"解析航班降落时间失败 eldt={eldt}: {e}")

            if flight_in_window:
                relevant.append(flight)

        return relevant

    def _match_affected_flights(
        self,
        flights: List[Dict[str, Any]],
        affected_stands: List[str],
        affected_runways: List[str],
        affected_taxiways: List[str]
    ) -> List[Dict[str, Any]]:
        """匹配受影响的航班"""
        affected = []

        # 加载拓扑用于查找
        topology = get_topology_loader()

        for flight in flights:
            stand = flight.get('stand')
            runway = flight.get('runway')
            impact_type = []
            impact_severity = 0

            # 检查机位影响
            if stand:
                # 尝试匹配受影响机位
                for affected_stand in affected_stands:
                    if stand in affected_stand or affected_stand in stand:
                        impact_type.append('stand')
                        impact_severity = max(impact_severity, 3)
                        break

            # 检查跑道影响
            if runway:
                for affected_runway in affected_runways:
                    if runway in affected_runway or affected_runway in runway:
                        impact_type.append('runway')
                        impact_severity = max(impact_severity, 3)
                        break

            # 检查滑行道影响（机位连接的滑行道）
            if stand and affected_taxiways:
                # 查找机位信息
                stand_info = topology.get_stand_info(stand)
                if stand_info:
                    adjacent_taxiways = stand_info.get('adjacent_taxiways', [])
                    for twy in adjacent_taxiways:
                        if twy in affected_taxiways:
                            impact_type.append('taxiway')
                            impact_severity = max(impact_severity, 2)
                            break

            if impact_type:
                flight_copy = flight.copy()
                flight_copy['impact_type'] = impact_type
                flight_copy['impact_severity'] = impact_severity
                affected.append(flight_copy)

        return affected

    def _calculate_delays(
        self,
        affected_flights: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算延误"""
        flights_with_delays = []
        total_delay = 0
        delay_distribution = {
            "stand_blocked": 0,
            "taxiway_blocked": 0,
            "runway_blocked": 0
        }

        for flight in affected_flights:
            impact_types = flight.get('impact_type', [])

            # 确定航班类型（到达/出发）
            is_departure = bool(flight.get('etot') or flight.get('atot'))
            is_arrival = bool(flight.get('eldt') or flight.get('aldt'))

            flight_type = 'departure' if is_departure else 'arrival'

            # 计算延误（取最大值）
            delay = 0
            delay_reason = []

            if 'runway' in impact_types:
                delay = max(delay, DELAY_RULES['runway_blocked'][flight_type])
                delay_reason.append('跑道封锁')
                delay_distribution["runway_blocked"] += 1

            if 'stand' in impact_types:
                delay = max(delay, DELAY_RULES['stand_blocked'][flight_type])
                delay_reason.append('机位封锁')
                delay_distribution["stand_blocked"] += 1

            if 'taxiway' in impact_types:
                delay = max(delay, DELAY_RULES['taxiway_blocked'][flight_type])
                delay_reason.append('滑行道封锁')
                delay_distribution["taxiway_blocked"] += 1

            flights_with_delays.append({
                'callsign': flight.get('callsign', 'UNKNOWN'),
                'stand': flight.get('stand', 'N/A'),
                'runway': flight.get('runway', 'N/A'),
                'type': flight_type,
                'estimated_delay_minutes': delay,
                'delay_reason': ', '.join(delay_reason),
                'impact_severity': flight.get('impact_severity', 1)
            })

            total_delay += delay

        # 排序（按延误从大到小）
        flights_with_delays.sort(key=lambda x: x['estimated_delay_minutes'], reverse=True)

        return {
            "flights": flights_with_delays,
            "statistics": {
                "total_affected_flights": len(flights_with_delays),
                "total_delay_minutes": total_delay,
                "average_delay_minutes": total_delay / len(flights_with_delays) if flights_with_delays else 0,
                "delay_distribution": delay_distribution,
                "severity_distribution": {
                    "high": sum(1 for f in flights_with_delays if (f.get('estimated_delay_minutes') or 0) >= 60),
                    "medium": sum(1 for f in flights_with_delays if 20 <= (f.get('estimated_delay_minutes') or 0) < 60),
                    "low": sum(1 for f in flights_with_delays if (f.get('estimated_delay_minutes') or 0) < 20)
                }
            }
        }

    def _generate_observation(
        self,
        impact_details: Dict[str, Any],
        time_window_hours: int,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """生成观测结果"""
        stats = impact_details["statistics"]
        flights = impact_details["flights"]

        observation = (
            f"航班影响预测完成（基于历史数据）:\n"
            f"时间窗口: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({time_window_hours}小时)\n"
            f"受影响航班总数: {stats['total_affected_flights']} 架次\n"
            f"累计延误时间: {stats['total_delay_minutes']} 分钟\n"
            f"平均延误: {stats['average_delay_minutes']:.1f} 分钟/架次\n"
        )

        # 添加严重程度分布
        sev = stats['severity_distribution']
        observation += (
            f"影响分布: 严重 {sev['high']} 架次, "
            f"中等 {sev['medium']} 架次, "
            f"轻微 {sev['low']} 架次\n"
        )

        # 列出前5个受影响最严重的航班
        if flights:
            observation += "\n受影响最严重的航班（前5）:\n"
            for i, flight in enumerate(flights[:5], 1):
                observation += (
                    f"{i}. {flight['callsign']}: "
                    f"延误 {flight['estimated_delay_minutes']} 分钟 "
                    f"({flight['delay_reason']}, "
                    f"机位={flight['stand']}, "
                    f"跑道={flight['runway']})\n"
                )

        return observation.strip()
