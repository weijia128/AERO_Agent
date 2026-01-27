import { Progress, Tag, Typography } from 'antd';
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';

const { Text } = Typography;

const riskToolNames = new Set([
  'assess_risk',
  'assess_oil_spill_risk',
  'assess_bird_strike_risk',
  'assess_fod_risk',
  'assess_weather_impact',
]);

export function CrossValidation() {
  const { riskAssessment, currentToolCalls, incident } = useSessionStore();
  const { bigScreenMode } = useUIStore();

  const crossValidation = riskAssessment?.cross_validation;
  const validationReport = riskAssessment?.validation_report as Record<string, unknown> | undefined;

  if (!crossValidation) {
    const scenarioType = incident?.scenario_type;
    const message =
      scenarioType && scenarioType !== 'oil_spill'
        ? '该场景未启用 LLM 交叉验证'
        : '交叉验证未返回（可能未启用或采样跳过）';
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
        {message}
      </div>
    );
  }

  const { rule_result, rule_score, llm_result, llm_confidence, consistent, needs_review } =
    crossValidation;
  const llmReasoning =
    (validationReport?.llm_validation as Record<string, unknown> | undefined)?.reasoning;
  const resolution =
    (validationReport?.final_decision as Record<string, unknown> | undefined)
      ?.resolution_strategy;
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
      : rule_result
      ? 'completed'
      : 'pending';
  const step2Status =
    llm_confidence > 0
      ? 'completed'
      : step1Status === 'completed'
      ? 'running'
      : step1Status === 'failed'
      ? 'failed'
      : 'pending';
  const step3Status =
    consistent || needs_review || rule_result
      ? 'completed'
      : step2Status === 'completed'
      ? 'running'
      : step2Status === 'failed'
      ? 'failed'
      : 'pending';
  const steps = [
    { label: '规则引擎输出', status: step1Status },
    { label: 'LLM 置信度评估', status: step2Status },
    { label: '一致性判定', status: step3Status },
  ];

  // 一致性状态
  const getConsistencyInfo = () => {
    if (consistent) {
      return {
        icon: <CheckCircleOutlined />,
        color: 'var(--accent-green)',
        text: '结果一致',
        bg: 'rgba(35, 134, 54, 0.15)',
      };
    } else if (needs_review) {
      return {
        icon: <WarningOutlined />,
        color: 'var(--danger)',
        text: '需人工复核',
        bg: 'rgba(248, 81, 73, 0.15)',
      };
    } else {
      return {
        icon: <ExclamationCircleOutlined />,
        color: 'var(--warning)',
        text: '存在差异',
        bg: 'rgba(210, 153, 34, 0.15)',
      };
    }
  };

  const consistencyInfo = getConsistencyInfo();

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: bigScreenMode ? 12 : 8,
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
          验证过程
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

      {/* 双引擎对比 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: bigScreenMode ? 12 : 8,
        }}
      >
        {/* 规则引擎 */}
        <div
          style={{
            padding: bigScreenMode ? '12px' : '8px',
            background: 'var(--bg-primary)',
            borderRadius: 6,
            textAlign: 'center',
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
            📐 规则引擎
          </Text>
          <Tag
            style={{
              fontSize: bigScreenMode ? 18 : 14,
              padding: bigScreenMode ? '4px 12px' : '2px 8px',
              fontWeight: 700,
              background: 'var(--accent-blue)',
              borderColor: 'var(--accent-blue)',
              color: '#fff',
            }}
          >
            {rule_result}
          </Tag>
          <Text
            style={{
              display: 'block',
              marginTop: 8,
              color: 'var(--text-primary)',
              fontSize: bigScreenMode ? 14 : 12,
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            {rule_score}分
          </Text>
        </div>

        {/* LLM 验证 */}
        <div
          style={{
            padding: bigScreenMode ? '12px' : '8px',
            background: 'var(--bg-primary)',
            borderRadius: 6,
            textAlign: 'center',
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
            🧠 LLM 验证
          </Text>
          <Tag
            style={{
              fontSize: bigScreenMode ? 18 : 14,
              padding: bigScreenMode ? '4px 12px' : '2px 8px',
              fontWeight: 700,
              background: 'var(--accent-green)',
              borderColor: 'var(--accent-green)',
              color: '#fff',
            }}
          >
            {llm_result}
          </Tag>
          <Text
            style={{
              display: 'block',
              marginTop: 8,
              color: 'var(--text-primary)',
              fontSize: bigScreenMode ? 14 : 12,
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            置信度 {(llm_confidence * 100).toFixed(0)}%
          </Text>
        </div>
      </div>

      {/* 置信度进度条 */}
      <div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 4,
          }}
        >
          <Text
            style={{
              color: 'var(--text-secondary)',
              fontSize: bigScreenMode ? 12 : 10,
            }}
          >
            LLM 置信度
          </Text>
          <Text
            style={{
              color:
                llm_confidence >= 0.85
                  ? 'var(--accent-green)'
                  : llm_confidence >= 0.75
                  ? 'var(--warning)'
                  : 'var(--danger)',
              fontSize: bigScreenMode ? 12 : 10,
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            {(llm_confidence * 100).toFixed(0)}%
          </Text>
        </div>
        <Progress
          percent={llm_confidence * 100}
          showInfo={false}
          strokeColor={
            llm_confidence >= 0.85
              ? 'var(--accent-green)'
              : llm_confidence >= 0.75
              ? 'var(--warning)'
              : 'var(--danger)'
          }
          trailColor="var(--border)"
          size={bigScreenMode ? 'default' : 'small'}
        />
      </div>

      {/* 一致性状态 */}
      <div
        style={{
          padding: bigScreenMode ? '10px 12px' : '8px 10px',
          background: consistencyInfo.bg,
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ color: consistencyInfo.color, fontSize: bigScreenMode ? 18 : 14 }}>
          {consistencyInfo.icon}
        </span>
        <Text
          style={{
            color: consistencyInfo.color,
            fontSize: bigScreenMode ? 13 : 11,
            fontWeight: 500,
          }}
        >
          {consistencyInfo.text}
          {consistent && '，使用规则引擎结果'}
          {!consistent && !needs_review && '，采用更严格等级'}
        </Text>
      </div>

      {(llmReasoning || resolution) && (
        <div
          style={{
            padding: bigScreenMode ? '10px 12px' : '8px 10px',
            background: 'var(--bg-primary)',
            borderRadius: 6,
            border: '1px solid var(--border)',
            fontSize: bigScreenMode ? 12 : 10,
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
          }}
        >
          {llmReasoning && (
            <div style={{ marginBottom: resolution ? 6 : 0 }}>
              LLM 说明: {llmReasoning}
            </div>
          )}
          {resolution && (
            <div>
              决策策略: {resolution}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
