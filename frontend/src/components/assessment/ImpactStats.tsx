import { Typography } from 'antd';
import {
  RocketOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  AlertOutlined,
} from '@ant-design/icons';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';

const { Text } = Typography;

export function ImpactStats() {
  const { flightImpact, spatialAnalysis } = useSessionStore();
  const { bigScreenMode } = useUIStore();

  const stats = [
    {
      icon: <RocketOutlined />,
      label: '受影响航班',
      value: flightImpact?.affected_count || 0,
      suffix: '架',
      color: 'var(--danger)',
    },
    {
      icon: <ClockCircleOutlined />,
      label: '累计延误',
      value: flightImpact?.total_delay_minutes || 0,
      suffix: '分钟',
      color: 'var(--warning)',
    },
    {
      icon: <EnvironmentOutlined />,
      label: '影响机位',
      value: spatialAnalysis?.affected_stands.length || 0,
      suffix: '个',
      color: 'var(--accent-blue)',
    },
    {
      icon: <AlertOutlined />,
      label: '影响跑道',
      value: spatialAnalysis?.affected_runways.length || 0,
      suffix: '条',
      color: spatialAnalysis?.affected_runways.length ? 'var(--danger)' : 'var(--accent-green)',
    },
  ];

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: bigScreenMode ? 12 : 8,
      }}
    >
      {stats.map((stat, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: bigScreenMode ? '10px 12px' : '8px 10px',
            background: 'var(--bg-primary)',
            borderRadius: 6,
            borderLeft: `3px solid ${stat.color}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: stat.color, fontSize: bigScreenMode ? 18 : 14 }}>
              {stat.icon}
            </span>
            <Text
              style={{
                color: 'var(--text-secondary)',
                fontSize: bigScreenMode ? 13 : 11,
              }}
            >
              {stat.label}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
            <Text
              style={{
                color: stat.value > 0 ? stat.color : 'var(--text-primary)',
                fontSize: bigScreenMode ? 20 : 16,
                fontWeight: 700,
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              {stat.value}
            </Text>
            <Text
              style={{
                color: 'var(--text-secondary)',
                fontSize: bigScreenMode ? 12 : 10,
              }}
            >
              {stat.suffix}
            </Text>
          </div>
        </div>
      ))}

      {/* 延误分布 */}
      {flightImpact && flightImpact.affected_count > 0 && (
        <div
          style={{
            marginTop: bigScreenMode ? 8 : 4,
            padding: bigScreenMode ? '10px 12px' : '8px 10px',
            background: 'var(--bg-primary)',
            borderRadius: 6,
          }}
        >
          <Text
            style={{
              color: 'var(--text-secondary)',
              fontSize: bigScreenMode ? 12 : 10,
              display: 'block',
              marginBottom: 8,
            }}
          >
            延误分布:
          </Text>
          <div style={{ display: 'flex', gap: bigScreenMode ? 12 : 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div
                style={{
                  width: 10,
                  height: 10,
                  background: 'var(--danger)',
                  borderRadius: 2,
                }}
              />
              <Text style={{ color: 'var(--text-primary)', fontSize: bigScreenMode ? 12 : 10 }}>
                严重: {flightImpact.delay_distribution.severe}
              </Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div
                style={{
                  width: 10,
                  height: 10,
                  background: 'var(--warning)',
                  borderRadius: 2,
                }}
              />
              <Text style={{ color: 'var(--text-primary)', fontSize: bigScreenMode ? 12 : 10 }}>
                中等: {flightImpact.delay_distribution.moderate}
              </Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div
                style={{
                  width: 10,
                  height: 10,
                  background: '#fadb14',
                  borderRadius: 2,
                }}
              />
              <Text style={{ color: 'var(--text-primary)', fontSize: bigScreenMode ? 12 : 10 }}>
                轻微: {flightImpact.delay_distribution.minor}
              </Text>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
