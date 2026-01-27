import { Space, Typography, Tag } from 'antd';
import {
  DatabaseOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { useUIStore } from '../../stores/uiStore';
import { useSessionStore } from '../../stores/sessionStore';

const { Text } = Typography;

export function Footer() {
  const { demoMode, bigScreenMode } = useUIStore();
  const { riskAssessment } = useSessionStore();

  const crossValidation = riskAssessment?.cross_validation;
  const isConsistent = crossValidation?.consistent ?? true;
  const confidence = crossValidation?.llm_confidence ?? 0;

  return (
    <footer
      style={{
        background: 'var(--bg-card)',
        borderTop: '1px solid var(--border)',
        padding: bigScreenMode ? '12px 32px' : '8px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      {/* 左侧：数据源信息 */}
      <Space size={bigScreenMode ? 24 : 16}>
        <Space size={8}>
          <DatabaseOutlined style={{ color: 'var(--text-secondary)' }} />
          <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 14 : 12 }}>
            数据源:
          </Text>
          <Tag
            color={demoMode ? 'default' : 'blue'}
            style={{ fontSize: bigScreenMode ? 13 : 11 }}
          >
            {demoMode ? '历史数据' : '实时数据'}
          </Tag>
        </Space>

        <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 14 : 12 }}>
          航班计划: 2026-01-06
        </Text>

        <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 14 : 12 }}>
          天气: ZBAA 10:00 UTC
        </Text>
      </Space>

      {/* 右侧：合规与验证状态 */}
      <Space size={bigScreenMode ? 24 : 16}>
        <Space size={8}>
          <SafetyCertificateOutlined
            style={{ color: 'var(--accent-green)' }}
          />
          <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 14 : 12 }}>
            合规校验:
          </Text>
          <Tag color="success" style={{ fontSize: bigScreenMode ? 13 : 11 }}>
            FSM <CheckCircleOutlined />
          </Tag>
        </Space>

        {crossValidation && (
          <>
            <Space size={8}>
              <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 14 : 12 }}>
                交叉验证:
              </Text>
              <Tag
                color={isConsistent ? 'success' : 'warning'}
                style={{ fontSize: bigScreenMode ? 13 : 11 }}
              >
                {isConsistent ? '一致' : '差异'}
              </Tag>
            </Space>

            <Space size={8}>
              <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 14 : 12 }}>
                置信度:
              </Text>
              <Text
                style={{
                  color: confidence >= 0.85 ? 'var(--accent-green)' : 'var(--warning)',
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: bigScreenMode ? 14 : 12,
                }}
              >
                {(confidence * 100).toFixed(0)}%
              </Text>
            </Space>
          </>
        )}
      </Space>
    </footer>
  );
}
