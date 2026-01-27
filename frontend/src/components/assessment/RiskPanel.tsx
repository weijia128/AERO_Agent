import { useEffect, useState } from 'react';
import { Progress, Tag, Typography } from 'antd';
import { DownOutlined, RightOutlined } from '@ant-design/icons';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';
import type { RiskLevel } from '../../types';

const { Text } = Typography;

// 风险等级配置
const riskConfig: Record<RiskLevel, { color: string; label: string; description: string }> = {
  R1: { color: '#238636', label: '低风险', description: '常规处理，无需紧急响应' },
  R2: { color: '#1f6feb', label: '中低风险', description: '加强监控，准备应急措施' },
  R3: { color: '#d29922', label: '中高风险', description: '启动应急程序，通知相关部门' },
  R4: { color: '#f85149', label: '高风险', description: '立即响应，全面启动应急预案' },
};

const riskToolNames = new Set([
  'assess_risk',
  'assess_oil_spill_risk',
  'assess_bird_strike_risk',
  'assess_fod_risk',
  'assess_weather_impact',
]);

export function RiskPanel() {
  const { riskAssessment, currentToolCalls } = useSessionStore();
  const { bigScreenMode } = useUIStore();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [visibleRuleCount, setVisibleRuleCount] = useState(0);
  const [visibleFactorCount, setVisibleFactorCount] = useState(0);

  // 计算派生状态（在 hooks 之后，条件 return 之前）
  const config = riskAssessment ? riskConfig[riskAssessment.level] : null;
  const rules = riskAssessment?.rules_triggered || [];
  const scoreBasis = (riskAssessment?.factors && riskAssessment.factors.length > 0)
    ? riskAssessment.factors
    : riskAssessment
    ? [
        `规则得分汇总: ${riskAssessment.score}分`,
        `等级映射: ${riskAssessment.level}`,
      ]
    : [];
  const riskToolCall = currentToolCalls.find((call) => riskToolNames.has(call.tool_name));
  const step1Status =
    riskToolCall?.status === 'completed'
      ? 'completed'
      : riskToolCall?.status === 'failed'
      ? 'failed'
      : riskToolCall?.status === 'running'
      ? 'running'
      : riskToolCall?.status === 'pending'
      ? 'pending'
      : riskAssessment?.level
      ? 'completed'
      : 'pending';
  const step2Status =
    rules.length > 0
      ? 'completed'
      : step1Status === 'completed'
      ? 'running'
      : step1Status === 'failed'
      ? 'failed'
      : 'pending';
  const step3Status =
    riskAssessment?.level
      ? 'completed'
      : step2Status === 'completed'
      ? 'running'
      : step2Status === 'failed'
      ? 'failed'
      : 'pending';
  const steps = [
    { label: '规则引擎计算', status: step1Status },
    { label: '触发规则汇总', status: step2Status },
    { label: '评分输出', status: step3Status },
  ];

  // useEffect 必须在所有条件 return 之前
  useEffect(() => {
    if (!detailsOpen || !riskAssessment) {
      setVisibleRuleCount(0);
      setVisibleFactorCount(0);
      return;
    }
    setVisibleRuleCount(0);
    setVisibleFactorCount(0);
    let ruleIndex = 0;
    let factorIndex = 0;
    let ruleTimer: ReturnType<typeof setInterval> | null = null;
    let factorTimer: ReturnType<typeof setInterval> | null = null;
    if (rules.length > 0) {
      ruleTimer = setInterval(() => {
        ruleIndex += 1;
        setVisibleRuleCount((prev) => Math.min(prev + 1, rules.length));
        if (ruleIndex >= rules.length && ruleTimer) {
          clearInterval(ruleTimer);
        }
      }, 140);
    }
    if (scoreBasis.length > 0) {
      factorTimer = setInterval(() => {
        factorIndex += 1;
        setVisibleFactorCount((prev) => Math.min(prev + 1, scoreBasis.length));
        if (factorIndex >= scoreBasis.length && factorTimer) {
          clearInterval(factorTimer);
        }
      }, 140);
    }
    return () => {
      if (ruleTimer) clearInterval(ruleTimer);
      if (factorTimer) clearInterval(factorTimer);
    };
  }, [
    detailsOpen,
    riskAssessment,
    rules.length,
    scoreBasis.length,
  ]);

  // 条件 return 必须在所有 hooks 之后
  if (!riskAssessment || !config) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-secondary)',
          fontSize: bigScreenMode ? 14 : 12,
        }}
      >
        等待风险评估...
      </div>
    );
  }

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: bigScreenMode ? 16 : 12,
      }}
    >
      {/* 过程展示 */}
      <div
        style={{
          padding: bigScreenMode ? '8px 10px' : '6px 8px',
          background: 'var(--bg-primary)',
          borderRadius: 6,
          border: '1px dashed var(--border)',
        }}
      >
        <Text
          style={{
            color: 'var(--text-secondary)',
            fontSize: bigScreenMode ? 12 : 10,
            display: 'block',
            marginBottom: 6,
          }}
        >
          评估过程
        </Text>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {steps.map((step) => {
            const color =
              step.status === 'completed'
                ? 'var(--accent-green)'
                : step.status === 'running'
                ? 'var(--accent-blue)'
                : step.status === 'failed'
                ? 'var(--danger)'
                : 'var(--text-secondary)';
            const dot =
              step.status === 'completed'
                ? '●'
                : step.status === 'running'
                ? '◐'
                : step.status === 'failed'
                ? '×'
                : '○';
            return (
              <div
                key={step.label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: bigScreenMode ? 12 : 10,
                }}
              >
                <span style={{ color }}>{dot}</span>
                <Text style={{ color }}>{step.label}</Text>
              </div>
            );
          })}
        </div>
      </div>

      {/* 风险等级展示 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <Tag
            style={{
              fontSize: bigScreenMode ? 20 : 16,
              padding: bigScreenMode ? '4px 16px' : '2px 12px',
              fontWeight: 700,
              background: config.color,
              borderColor: config.color,
              color: '#fff',
            }}
          >
            {riskAssessment.level}
          </Tag>
          <Text
            style={{
              marginLeft: 12,
              color: config.color,
              fontSize: bigScreenMode ? 16 : 14,
              fontWeight: 600,
            }}
          >
            {config.label}
          </Text>
        </div>
        <Text
          style={{
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 24 : 20,
            fontWeight: 700,
            fontFamily: 'JetBrains Mono, monospace',
          }}
        >
          {riskAssessment.score}分
        </Text>
      </div>

      {/* 进度条 */}
      <Progress
        percent={riskAssessment.score}
        showInfo={false}
        strokeColor={config.color}
        trailColor="var(--border)"
        size={bigScreenMode ? 'default' : 'small'}
      />

      {/* 风险描述 */}
      <div
        style={{
          padding: bigScreenMode ? '10px 12px' : '8px 10px',
          background: `${config.color}20`,
          borderRadius: 6,
          borderLeft: `3px solid ${config.color}`,
        }}
      >
        <Text
          style={{
            color: config.color,
            fontSize: bigScreenMode ? 13 : 11,
          }}
        >
          {config.description}
        </Text>
      </div>

      {/* 详情折叠 */}
      <div>
        <div
          onClick={() => setDetailsOpen(!detailsOpen)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: bigScreenMode ? '8px 10px' : '6px 8px',
            background: 'var(--bg-primary)',
            borderRadius: 6,
            cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text
              style={{
                color: 'var(--text-primary)',
                fontSize: bigScreenMode ? 12 : 10,
                fontWeight: 500,
              }}
            >
              详情
            </Text>
            <Text
              style={{
                color: 'var(--text-secondary)',
                fontSize: bigScreenMode ? 11 : 9,
              }}
            >
              规则 {rules.length} 条 · 依据 {scoreBasis.length} 条
            </Text>
          </div>
          {detailsOpen ? (
            <DownOutlined style={{ fontSize: 12, color: 'var(--text-secondary)' }} />
          ) : (
            <RightOutlined style={{ fontSize: 12, color: 'var(--text-secondary)' }} />
          )}
        </div>

        {detailsOpen && (
          <div
            style={{
              marginTop: 8,
              padding: bigScreenMode ? '10px 12px' : '8px 10px',
              background: 'var(--bg-primary)',
              borderRadius: 6,
              border: '1px solid var(--border)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div>
              <Text
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: bigScreenMode ? 12 : 10,
                  display: 'block',
                  marginBottom: 6,
                }}
              >
                触发规则
              </Text>
              {rules.length === 0 ? (
                <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 12 : 10 }}>
                  暂无规则
                </Text>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {rules.slice(0, visibleRuleCount).map((rule, index) => (
                    <div
                      key={`${rule}-${index}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: bigScreenMode ? '6px 10px' : '4px 8px',
                        background: 'var(--bg-card)',
                        borderRadius: 4,
                        fontSize: bigScreenMode ? 12 : 10,
                      }}
                    >
                      <span style={{ color: 'var(--warning)' }}>•</span>
                      <Text
                        style={{
                          color: 'var(--text-primary)',
                          fontFamily: 'monospace',
                        }}
                      >
                        {rule}
                      </Text>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <Text
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: bigScreenMode ? 12 : 10,
                  display: 'block',
                  marginBottom: 6,
                }}
              >
                评分依据
              </Text>
              {scoreBasis.length === 0 ? (
                <Text style={{ color: 'var(--text-secondary)', fontSize: bigScreenMode ? 12 : 10 }}>
                  暂无依据
                </Text>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {scoreBasis.slice(0, visibleFactorCount).map((item, index) => (
                    <div
                      key={`${item}-${index}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: bigScreenMode ? '6px 10px' : '4px 8px',
                        background: 'var(--bg-card)',
                        borderRadius: 4,
                        fontSize: bigScreenMode ? 12 : 10,
                      }}
                    >
                      <span style={{ color: 'var(--accent-blue)' }}>•</span>
                      <Text
                        style={{
                          color: 'var(--text-primary)',
                          fontFamily: 'monospace',
                        }}
                      >
                        {item}
                      </Text>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
