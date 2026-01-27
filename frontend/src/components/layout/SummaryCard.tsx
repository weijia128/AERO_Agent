import { Card, Space, Tag, Typography } from 'antd';
import {
  AlertOutlined,
  EnvironmentOutlined,
  FireOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';
import type { RiskLevel, FluidType } from '../../types';

const { Text } = Typography;

// 风险等级配置
const riskConfig: Record<RiskLevel, { color: string; label: string; bgColor: string }> = {
  R1: { color: '#238636', label: '低风险', bgColor: 'rgba(35, 134, 54, 0.2)' },
  R2: { color: '#1f6feb', label: '中低风险', bgColor: 'rgba(31, 111, 235, 0.2)' },
  R3: { color: '#d29922', label: '中高风险', bgColor: 'rgba(210, 153, 34, 0.2)' },
  R4: { color: '#f85149', label: '高风险', bgColor: 'rgba(248, 81, 73, 0.2)' },
};

// 油液类型配置
const fluidConfig: Record<FluidType, { icon: React.ReactNode; label: string }> = {
  FUEL: { icon: <FireOutlined />, label: '燃油' },
  HYDRAULIC: { icon: <AlertOutlined />, label: '液压油' },
  OIL: { icon: <AlertOutlined />, label: '润滑油' },
  UNKNOWN: { icon: <ExclamationCircleOutlined />, label: '未知' },
};

export function SummaryCard() {
  const { incident, riskAssessment, fsmState } = useSessionStore();
  const { bigScreenMode } = useUIStore();

  // 如果没有事件信息，显示空状态
  if (!incident?.flight_no && !incident?.position) {
    return (
      <Card
        style={{
          background: 'var(--bg-card)',
          borderColor: 'var(--border)',
          marginBottom: 16,
        }}
        bodyStyle={{ padding: bigScreenMode ? '20px 24px' : '12px 16px' }}
      >
        <Text style={{ color: 'var(--text-secondary)' }}>
          等待事件输入...
        </Text>
      </Card>
    );
  }

  const risk = riskAssessment?.level;
  const riskInfo = risk ? riskConfig[risk] : null;
  const fluidInfo = incident?.fluid_type ? fluidConfig[incident.fluid_type] : null;

  // 生成智能结论
  const generateConclusion = () => {
    if (!riskAssessment) return '正在分析事件...';

    const parts: string[] = [];
    if (incident?.fluid_type) {
      parts.push(fluidInfo?.label + '泄漏');
    }
    if (incident?.continuous) {
      parts.push('持续滴漏');
    }
    if (incident?.engine_status === 'RUNNING') {
      parts.push('发动机运转中');
    }
    if (risk === 'R4' || risk === 'R3') {
      parts.push('需立即通知消防');
    }
    if (riskAssessment.cross_validation?.needs_review) {
      parts.push('建议人工复核');
    }

    return parts.length > 0 ? parts.join('，') : '事件分析中...';
  };

  return (
    <Card
      style={{
        background: 'var(--bg-card)',
        borderColor: risk ? riskInfo?.color : 'var(--border)',
        borderWidth: risk ? 2 : 1,
        marginBottom: 16,
      }}
      bodyStyle={{ padding: bigScreenMode ? '20px 24px' : '12px 16px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        {/* 左侧：事件信息标签 */}
        <Space size={bigScreenMode ? 16 : 12} wrap>
          {/* 航班号 */}
          {incident?.flight_no && (
            <Tag
              icon={<AlertOutlined />}
              style={{
                background: 'rgba(31, 111, 235, 0.2)',
                borderColor: 'var(--accent-blue)',
                color: 'var(--accent-blue)',
                fontSize: bigScreenMode ? 16 : 14,
                padding: bigScreenMode ? '4px 12px' : '2px 8px',
              }}
            >
              {incident.flight_no}
            </Tag>
          )}

          {/* 位置 */}
          {incident?.position && (
            <Tag
              icon={<EnvironmentOutlined />}
              style={{
                background: 'rgba(139, 148, 158, 0.2)',
                borderColor: 'var(--text-secondary)',
                color: 'var(--text-secondary)',
                fontSize: bigScreenMode ? 16 : 14,
                padding: bigScreenMode ? '4px 12px' : '2px 8px',
              }}
            >
              {incident.position}
            </Tag>
          )}

          {/* 油液类型 */}
          {fluidInfo && (
            <Tag
              icon={fluidInfo.icon}
              style={{
                background: 'rgba(210, 153, 34, 0.2)',
                borderColor: 'var(--warning)',
                color: 'var(--warning)',
                fontSize: bigScreenMode ? 16 : 14,
                padding: bigScreenMode ? '4px 12px' : '2px 8px',
              }}
            >
              {fluidInfo.label}
            </Tag>
          )}

          {/* 风险等级 */}
          {riskInfo && (
            <Tag
              style={{
                background: riskInfo.bgColor,
                borderColor: riskInfo.color,
                color: riskInfo.color,
                fontSize: bigScreenMode ? 16 : 14,
                padding: bigScreenMode ? '4px 12px' : '2px 8px',
                fontWeight: 600,
              }}
            >
              {risk} {riskInfo.label}
            </Tag>
          )}

          {/* FSM 状态 */}
          <Tag
            icon={fsmState === 'COMPLETED' ? <CheckCircleOutlined /> : undefined}
            style={{
              background: 'rgba(35, 134, 54, 0.2)',
              borderColor: 'var(--accent-green)',
              color: 'var(--accent-green)',
              fontSize: bigScreenMode ? 16 : 14,
              padding: bigScreenMode ? '4px 12px' : '2px 8px',
            }}
          >
            FSM: {fsmState}
          </Tag>
        </Space>
      </div>

      {/* 智能结论 */}
      <div
        style={{
          marginTop: bigScreenMode ? 16 : 12,
          padding: bigScreenMode ? '12px 16px' : '8px 12px',
          background: 'var(--bg-primary)',
          borderRadius: 6,
          borderLeft: `3px solid ${riskInfo?.color || 'var(--accent-blue)'}`,
        }}
      >
        <Text
          style={{
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 16 : 14,
          }}
        >
          {generateConclusion()}
        </Text>
      </div>
    </Card>
  );
}
