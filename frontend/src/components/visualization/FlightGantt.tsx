import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';

// 严重程度颜色
const severityColors: Record<string, string> = {
  severe: '#f85149',
  moderate: '#d29922',
  minor: '#fadb14',
  normal: '#238636',
};

// 解析时间为分钟数（从8:00开始）
function parseTimeToMinutes(timeStr: string): number {
  const match = timeStr.match(/(\d{2}):(\d{2})/);
  if (match) {
    const hours = parseInt(match[1], 10);
    const minutes = parseInt(match[2], 10);
    return (hours - 8) * 60 + minutes;
  }
  return 0;
}

// 格式化分钟为时间字符串
function formatMinutesToTime(minutes: number): string {
  const hours = Math.floor(minutes / 60) + 8;
  const mins = minutes % 60;
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

export function FlightGantt() {
  const { flightImpact } = useSessionStore();
  const { bigScreenMode } = useUIStore();

  const option = useMemo(() => {
    const flights = flightImpact?.flights || [];

    // 按计划时间排序
    const sortedFlights = [...flights].sort((a, b) => {
      const timeA = parseTimeToMinutes(a.scheduled_time || '');
      const timeB = parseTimeToMinutes(b.scheduled_time || '');
      return timeA - timeB;
    });

    // 生成数据
    const data = sortedFlights.map((flight, index) => {
      const startMinutes = parseTimeToMinutes(flight.scheduled_time || '');
      const duration = 30; // 假设每个航班持续30分钟
      const delayMinutes = flight.delay || 0;

      return {
        name: flight.callsign,
        value: [
          index, // Y轴位置
          startMinutes, // 开始时间
          startMinutes + duration, // 结束时间
          delayMinutes, // 延误时间
          flight.severity,
          flight.aircraft_type,
          flight.stand,
        ],
        itemStyle: {
          color: severityColors[flight.severity] || severityColors.normal,
        },
      };
    });

    // 延误数据（虚线延长部分）
    const delayData = sortedFlights
      .filter((f) => f.delay > 0)
      .map((flight) => {
        const startMinutes = parseTimeToMinutes(flight.scheduled_time || '');
        const duration = 30;
        const delayMinutes = flight.delay || 0;

        return {
          name: `${flight.callsign}-delay`,
          value: [
            sortedFlights.findIndex((f) => f.callsign === flight.callsign),
            startMinutes + duration,
            startMinutes + duration + delayMinutes,
          ],
          itemStyle: {
            color: 'transparent',
            borderColor: severityColors[flight.severity],
            borderWidth: 2,
            borderType: 'dashed',
          },
        };
      });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#161b22',
        borderColor: '#30363d',
        textStyle: {
          color: '#e6edf3',
        },
        formatter: (params: { value?: (string | number)[] }) => {
          if (params.value) {
            const [, start, end, delay, severity, type, stand] = params.value as (string | number)[];
            return `
              <div style="font-weight: 600; margin-bottom: 4px;">${sortedFlights[params.value[0] as number]?.callsign}</div>
              <div>机型: ${type}</div>
              <div>机位: ${stand}</div>
              <div>计划: ${formatMinutesToTime(start as number)} - ${formatMinutesToTime(end as number)}</div>
              ${delay ? `<div style="color: ${severityColors[severity as string]}">延误: ${delay} 分钟</div>` : ''}
            `;
          }
          return '';
        },
      },
      grid: {
        left: bigScreenMode ? 100 : 80,
        right: 20,
        top: 30,
        bottom: 50,
      },
      xAxis: {
        type: 'value',
        min: 0,
        max: 240, // 4小时 (8:00-12:00)
        interval: 30,
        axisLabel: {
          formatter: (value: number) => formatMinutesToTime(value),
          color: '#8b949e', // 替换 var(--text-secondary)
          fontSize: bigScreenMode ? 14 : 12,
        },
        axisLine: {
          lineStyle: {
            color: '#30363d', // 替换 var(--border)
          },
        },
        splitLine: {
          lineStyle: {
            color: '#30363d',
            type: 'dashed',
          },
        },
      },
      yAxis: {
        type: 'category',
        data: sortedFlights.map((f) => f.callsign),
        inverse: true,
        axisLabel: {
          color: '#e6edf3', // 替换 var(--text-primary)
          fontSize: bigScreenMode ? 14 : 12,
          fontFamily: 'JetBrains Mono, monospace',
        },
        axisLine: {
          lineStyle: {
            color: '#30363d',
          },
        },
        splitLine: {
          show: false,
        },
      },
      series: [
        {
          type: 'custom',
          renderItem: (_params: unknown, api: { value: (idx: number) => number; coord: (val: [number, number]) => [number, number]; size: (val: [number, number]) => [number, number]; style: (opt: object) => object }) => {
            const yIndex = api.value(0);
            const start = api.coord([api.value(1), yIndex]);
            const end = api.coord([api.value(2), yIndex]);
            const height = api.size([0, 1])[1] * 0.6;

            return {
              type: 'rect',
              shape: {
                x: start[0],
                y: start[1] - height / 2,
                width: end[0] - start[0],
                height: height,
                r: 3,
              },
              style: api.style({
                stroke: '#30363d', // 替换 var(--border)
                lineWidth: 1,
              }),
            };
          },
          encode: {
            x: [1, 2],
            y: 0,
          },
          data: [...data, ...delayData],
        },
      ],
    };
  }, [flightImpact, bigScreenMode]);

  // 如果没有数据，显示空状态
  if (!flightImpact || flightImpact.affected_count === 0) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-secondary)',
        }}
      >
        暂无航班影响数据
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <ReactECharts
        option={option}
        style={{ width: '100%', height: '100%' }}
        opts={{ renderer: 'canvas' }}
      />

      {/* 延误统计 */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          display: 'flex',
          gap: 12,
          fontSize: bigScreenMode ? 14 : 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 12, height: 12, background: severityColors.severe, borderRadius: 2 }} />
          <span style={{ color: 'var(--text-secondary)' }}>
            严重: {flightImpact.delay_distribution.severe}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 12, height: 12, background: severityColors.moderate, borderRadius: 2 }} />
          <span style={{ color: 'var(--text-secondary)' }}>
            中等: {flightImpact.delay_distribution.moderate}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 12, height: 12, background: severityColors.minor, borderRadius: 2 }} />
          <span style={{ color: 'var(--text-secondary)' }}>
            轻微: {flightImpact.delay_distribution.minor}
          </span>
        </div>
      </div>
    </div>
  );
}
