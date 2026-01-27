import { useUIStore } from '../../stores/uiStore';
import { mockWeather } from '../../services/mockData';

// 风向转换为方位
function getWindDirection(degrees: number): string {
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const index = Math.round(degrees / 45) % 8;
  return directions[index];
}

export function WeatherCard() {
  const { bigScreenMode } = useUIStore();
  const weather = mockWeather;

  const items = [
    {
      icon: '🌡️',
      label: '温度',
      value: `${weather.temperature}°C`,
      color: weather.temperature < 0 ? 'var(--accent-blue)' : 'var(--text-primary)',
    },
    {
      icon: '💨',
      label: '风速',
      value: `${weather.wind_speed}kt ${getWindDirection(weather.wind_direction)}`,
      color: weather.wind_speed > 20 ? 'var(--warning)' : 'var(--text-primary)',
    },
    {
      icon: '👁️',
      label: '能见度',
      value: weather.visibility >= 9999 ? '>10km' : `${weather.visibility}m`,
      color: weather.visibility < 5000 ? 'var(--warning)' : 'var(--accent-green)',
    },
    {
      icon: '💧',
      label: '湿度',
      value: `${weather.relative_humidity}%`,
      color: 'var(--text-primary)',
    },
  ];

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: bigScreenMode ? 12 : 8,
      }}
    >
      {items.map((item, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: bigScreenMode ? '8px 12px' : '4px 8px',
            background: 'var(--bg-primary)',
            borderRadius: 4,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: bigScreenMode ? 18 : 14 }}>{item.icon}</span>
            <span
              style={{
                color: 'var(--text-secondary)',
                fontSize: bigScreenMode ? 14 : 12,
              }}
            >
              {item.label}
            </span>
          </div>
          <span
            style={{
              color: item.color,
              fontSize: bigScreenMode ? 16 : 14,
              fontFamily: 'JetBrains Mono, monospace',
              fontWeight: 500,
            }}
          >
            {item.value}
          </span>
        </div>
      ))}

      {/* 天气影响说明 */}
      <div
        style={{
          marginTop: bigScreenMode ? 8 : 4,
          padding: bigScreenMode ? '8px 12px' : '4px 8px',
          background: 'rgba(35, 134, 54, 0.1)',
          borderRadius: 4,
          borderLeft: '3px solid var(--accent-green)',
        }}
      >
        <span
          style={{
            color: 'var(--accent-green)',
            fontSize: bigScreenMode ? 12 : 10,
          }}
        >
          天气条件良好，不影响清理作业
        </span>
      </div>
    </div>
  );
}
