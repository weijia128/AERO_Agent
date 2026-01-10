"""
时段分析工具

综合分析特定时段的航班计划和航迹数据
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
from pathlib import Path

try:
    from data_processing.parse_flight_plan import FlightPlanParser, filter_by_time_range as filter_plan
    from data_processing.parse_trajectory import TrajectoryParser, filter_by_time_range as filter_traj
except ModuleNotFoundError:
    from parse_flight_plan import FlightPlanParser, filter_by_time_range as filter_plan
    from parse_trajectory import TrajectoryParser, filter_by_time_range as filter_traj


class TimePeriodAnalyzer:
    """时段分析器"""

    def __init__(self, flight_plan_dir: str, trajectory_dir: str):
        self.flight_plan_dir = flight_plan_dir
        self.trajectory_dir = trajectory_dir
        self.flight_parser = FlightPlanParser()
        self.traj_parser = TrajectoryParser()

    def analyze(
        self,
        start_time: str,
        end_time: str,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析指定时段的数据

        Args:
            start_time: 开始时间 "2025-10-21 11:00:00"
            end_time: 结束时间 "2025-10-21 12:00:00"
            output_file: 输出文件路径（可选）
        """
        print("=" * 60)
        print(f"分析时段: {start_time} - {end_time}")
        print("=" * 60)

        # 1. 解析航班计划数据
        print("\n[1/5] 解析航班计划数据...")
        all_plans = self.flight_parser.parse_directory(self.flight_plan_dir)
        plans = filter_plan(all_plans, start_time, end_time, time_field="eldt")
        print(f"   ✓ 该时段航班计划: {len(plans)} 条")

        # 2. 解析航迹数据
        print("\n[2/5] 解析航迹数据...")
        # 确定需要读取的小时文件
        start_hour = datetime.fromisoformat(start_time).hour
        end_hour = datetime.fromisoformat(end_time).hour
        date_str = start_time.split()[0]

        all_trajectories = []
        for hour in range(start_hour, end_hour + 1):
            traj_file = f"{self.trajectory_dir}/{date_str}_{hour:02d}h.log"
            if Path(traj_file).exists():
                print(f"   读取: {Path(traj_file).name}")
                trajs = self.traj_parser.parse_file(traj_file)
                all_trajectories.extend(trajs)

        trajectories = filter_traj(all_trajectories, start_time, end_time)
        print(f"   ✓ 该时段航迹记录: {len(trajectories)} 条")

        # 3. 数据清洗与关联
        print("\n[3/5] 数据清洗与关联...")
        cleaned_data = self._clean_and_correlate(plans, trajectories)

        # 4. 统计分析
        print("\n[4/5] 统计分析...")
        statistics = self._calculate_statistics(cleaned_data)

        # 5. 生成报告
        print("\n[5/5] 生成分析报告...")
        report = {
            'time_period': {
                'start': start_time,
                'end': end_time,
                'duration_minutes': (
                    datetime.fromisoformat(end_time) -
                    datetime.fromisoformat(start_time)
                ).total_seconds() / 60
            },
            'data_summary': {
                'flight_plans': len(plans),
                'trajectory_records': len(trajectories),
            },
            'statistics': statistics,
            'cleaned_data': cleaned_data,
        }

        # 打印报告
        self._print_report(report)

        # 保存到文件
        if output_file:
            self._save_report(report, output_file)

        return report

    def _clean_and_correlate(
        self,
        plans: List[Dict[str, Any]],
        trajectories: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """清洗数据并关联航班计划和航迹"""

        # 按呼号分组航班计划
        plan_by_callsign = {}
        for plan in plans:
            callsign = plan.get('callsign')
            if callsign:
                plan_by_callsign[callsign] = plan

        # 按呼号分组航迹
        traj_by_callsign = defaultdict(list)
        for traj in trajectories:
            callsign = traj.get('CALLSIGN')
            if callsign and traj.get('targettype') == 'Aircraft':
                traj_by_callsign[callsign].append(traj)

        # 关联数据
        correlated_flights = []
        for callsign in plan_by_callsign:
            flight = {
                'callsign': callsign,
                'plan': plan_by_callsign[callsign],
                'trajectory': traj_by_callsign.get(callsign, []),
                'has_trajectory': callsign in traj_by_callsign,
            }
            correlated_flights.append(flight)

        # 机位使用情况
        stand_usage = defaultdict(list)
        for flight in correlated_flights:
            stand = flight['plan'].get('stand')
            if stand:
                stand_usage[stand].append(flight['callsign'])

        # 跑道使用情况
        runway_usage = defaultdict(list)
        for flight in correlated_flights:
            runway = flight['plan'].get('runway')
            if runway:
                runway_usage[runway].append(flight['callsign'])

        return {
            'correlated_flights': correlated_flights,
            'stand_usage': dict(stand_usage),
            'runway_usage': dict(runway_usage),
        }

    def _calculate_statistics(self, cleaned_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算统计指标"""
        flights = cleaned_data['correlated_flights']
        stand_usage = cleaned_data['stand_usage']
        runway_usage = cleaned_data['runway_usage']

        # 到达/起飞统计
        arrivals = [f for f in flights if f['plan'].get('inorout') == 'A']
        departures = [f for f in flights if f['plan'].get('inorout') == 'D']

        # 机位统计
        stand_stats = {
            stand: {
                'flight_count': len(flights),
                'flights': flights
            }
            for stand, flights in stand_usage.items()
        }
        # 按使用次数排序
        sorted_stands = sorted(
            stand_stats.items(),
            key=lambda x: x[1]['flight_count'],
            reverse=True
        )

        # 跑道统计
        runway_stats = {
            runway: {
                'flight_count': len(flights),
                'flights': flights
            }
            for runway, flights in runway_usage.items()
        }
        sorted_runways = sorted(
            runway_stats.items(),
            key=lambda x: x[1]['flight_count'],
            reverse=True
        )

        # 机位-跑道关系提取
        stand_runway_mapping = defaultdict(lambda: defaultdict(int))
        for flight in flights:
            stand = flight['plan'].get('stand')
            runway = flight['plan'].get('runway')
            if stand and runway:
                stand_runway_mapping[stand][runway] += 1

        return {
            'total_flights': len(flights),
            'arrivals': len(arrivals),
            'departures': len(departures),
            'flights_with_trajectory': sum(1 for f in flights if f['has_trajectory']),
            'unique_stands': len(stand_usage),
            'unique_runways': len(runway_usage),
            'stand_statistics': {
                'sorted_by_usage': [
                    {'stand': stand, **stats}
                    for stand, stats in sorted_stands[:10]  # Top 10
                ],
                'busiest_stand': sorted_stands[0] if sorted_stands else None,
            },
            'runway_statistics': {
                'sorted_by_usage': [
                    {'runway': runway, **stats}
                    for runway, stats in sorted_runways
                ],
                'busiest_runway': sorted_runways[0] if sorted_runways else None,
            },
            'stand_runway_mapping': {
                stand: dict(runways)
                for stand, runways in stand_runway_mapping.items()
            },
        }

    def _print_report(self, report: Dict[str, Any]):
        """打印分析报告"""
        stats = report['statistics']

        print("\n" + "=" * 60)
        print("分析报告")
        print("=" * 60)

        print(f"\n时段: {report['time_period']['start']} - {report['time_period']['end']}")
        print(f"时长: {report['time_period']['duration_minutes']:.0f} 分钟")

        print(f"\n数据概览:")
        print(f"  - 总航班数: {stats['total_flights']}")
        print(f"  - 到达航班: {stats['arrivals']}")
        print(f"  - 起飞航班: {stats['departures']}")
        print(f"  - 有航迹数据: {stats['flights_with_trajectory']}")

        print(f"\n机位统计:")
        print(f"  - 使用机位数: {stats['unique_stands']}")
        if stats['stand_statistics']['busiest_stand']:
            stand, data = stats['stand_statistics']['busiest_stand']
            print(f"  - 最繁忙机位: {stand} ({data['flight_count']} 个航班)")

        print(f"\n  Top 10 繁忙机位:")
        for item in stats['stand_statistics']['sorted_by_usage'][:10]:
            print(f"    {item['stand']}: {item['flight_count']} 个航班")

        print(f"\n跑道统计:")
        print(f"  - 使用跑道数: {stats['unique_runways']}")
        if stats['runway_statistics']['busiest_runway']:
            runway, data = stats['runway_statistics']['busiest_runway']
            print(f"  - 最繁忙跑道: {runway} ({data['flight_count']} 个航班)")

        print(f"\n机位-跑道映射关系 (前10个):")
        for i, (stand, runways) in enumerate(
            list(stats['stand_runway_mapping'].items())[:10]
        ):
            primary_runway = max(runways.items(), key=lambda x: x[1])
            print(f"  {stand}: 主要使用 {primary_runway[0]} ({primary_runway[1]}次)")

    def _save_report(self, report: Dict[str, Any], output_file: str):
        """保存报告到文件"""
        # 移除不可JSON序列化的部分
        clean_report = {
            'time_period': report['time_period'],
            'data_summary': report['data_summary'],
            'statistics': {
                k: v for k, v in report['statistics'].items()
                if k not in ['stand_statistics', 'runway_statistics']
            },
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(clean_report, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 报告已保存到: {output_file}")


if __name__ == "__main__":
    # 分析 2025-10-21 11:00-12:00 时段
    project_root = Path(__file__).resolve().parents[2]
    flight_plan_dir = project_root / "data" / "raw" / "航班计划"
    trajectory_dir = project_root / "data" / "raw" / "航迹数据"
    output_file = project_root / "scripts" / "data_processing" / "analysis_11_12.json"

    analyzer = TimePeriodAnalyzer(
        flight_plan_dir=str(flight_plan_dir),
        trajectory_dir=str(trajectory_dir),
    )

    report = analyzer.analyze(
        start_time="2025-10-21 11:00:00",
        end_time="2025-10-21 12:00:00",
        output_file=str(output_file)
    )
