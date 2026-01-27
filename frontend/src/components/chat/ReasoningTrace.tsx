import { useState } from 'react';
import { Typography } from 'antd';
import {
  CheckCircleOutlined,
  LoadingOutlined,
  CloseCircleOutlined,
  RightOutlined,
  DownOutlined,
  BulbOutlined,
  ToolOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';
import type { ToolCall, ToolStatus, ReasoningStep } from '../../types';

const { Text } = Typography;

// 工具图标映射
const toolIcons: Record<string, string> = {
  get_aircraft_info: '🔍',
  get_topology_info: '🗺️',
  get_weather: '🌤️',
  assess_oil_spill_risk: '⚠️',
  assess_risk: '⚠️',
  analyze_impact_zone: '📍',
  analyze_spill_comprehensive: '📊',
  predict_flight_impact: '✈️',
  notify_department: '🔔',
  generate_report: '📋',
  ask: '❓',
  smart_ask: '💬',
  flight_plan_lookup: '✈️',
};

// 状态图标
const statusIcons: Record<ToolStatus, React.ReactNode> = {
  pending: <span style={{ color: 'var(--text-secondary)' }}>⏳</span>,
  running: <LoadingOutlined style={{ color: 'var(--accent-blue)' }} />,
  completed: <CheckCircleOutlined style={{ color: 'var(--accent-green)' }} />,
  failed: <CloseCircleOutlined style={{ color: 'var(--danger)' }} />,
};

interface ToolCallItemProps {
  toolCall: ToolCall;
  bigScreenMode: boolean;
}

function ToolCallItem({ toolCall, bigScreenMode }: ToolCallItemProps) {
  const [expanded, setExpanded] = useState(false);
  const icon = toolIcons[toolCall.tool_name] || '🔧';

  return (
    <div
      style={{
        marginBottom: bigScreenMode ? 8 : 6,
        background: 'var(--bg-primary)',
        borderRadius: 4,
        overflow: 'hidden',
      }}
    >
      {/* 工具调用头部 */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: bigScreenMode ? '8px 12px' : '6px 10px',
          cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: bigScreenMode ? 14 : 12 }}>{icon}</span>
        <Text
          style={{
            flex: 1,
            color: 'var(--text-primary)',
            fontSize: bigScreenMode ? 13 : 11,
            fontFamily: 'monospace',
          }}
        >
          {toolCall.tool_name}
        </Text>
        {statusIcons[toolCall.status]}
        {toolCall.output && (
          expanded ? (
            <DownOutlined style={{ fontSize: 10, color: 'var(--text-secondary)' }} />
          ) : (
            <RightOutlined style={{ fontSize: 10, color: 'var(--text-secondary)' }} />
          )
        )}
      </div>

      {/* 展开的详情 */}
      {expanded && toolCall.output && (
        <div
          style={{
            padding: bigScreenMode ? '8px 12px' : '6px 10px',
            borderTop: '1px solid var(--border)',
            fontSize: bigScreenMode ? 12 : 10,
            color: 'var(--text-secondary)',
            fontFamily: 'monospace',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {toolCall.output}
        </div>
      )}
    </div>
  );
}

interface ReasoningStepItemProps {
  step: ReasoningStep;
  bigScreenMode: boolean;
}

function getReasoningSummary(step: ReasoningStep): string {
  if (step.action) {
    return `调用工具: ${step.action}`;
  }
  if (step.observation) {
    return '处理工具反馈';
  }
  return '推理更新';
}

function ReasoningStepItem({ step, bigScreenMode }: ReasoningStepItemProps) {
  const [expanded, setExpanded] = useState(false);
  const actionIcon = step.action ? (toolIcons[step.action] || '🔧') : '💭';
  const summary = getReasoningSummary(step);

  return (
    <div
      style={{
        marginBottom: bigScreenMode ? 12 : 8,
        background: 'var(--bg-primary)',
        borderRadius: 6,
        border: '1px solid var(--border)',
        overflow: 'hidden',
      }}
    >
      {/* 步骤头部 */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          padding: bigScreenMode ? '10px 12px' : '8px 10px',
          cursor: 'pointer',
          background: 'var(--bg-card)',
        }}
      >
        <span
          style={{
            background: 'var(--accent-blue)',
            color: '#fff',
            fontSize: bigScreenMode ? 11 : 9,
            padding: '2px 8px',
            borderRadius: 10,
            fontWeight: 600,
          }}
        >
          Step {step.step}
        </span>
        <div style={{ flex: 1 }}>
          {/* 推理摘要 */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
            <BulbOutlined style={{ color: 'var(--warning)', marginTop: 2 }} />
            <Text
              style={{
                color: 'var(--text-primary)',
                fontSize: bigScreenMode ? 13 : 11,
                lineHeight: 1.5,
              }}
            >
              {summary}
            </Text>
          </div>
        </div>
        {(step.action || step.observation) && (
          expanded ? (
            <DownOutlined style={{ fontSize: 10, color: 'var(--text-secondary)' }} />
          ) : (
            <RightOutlined style={{ fontSize: 10, color: 'var(--text-secondary)' }} />
          )
        )}
      </div>

      {/* 展开的详情 */}
      {expanded && (step.action || step.observation) && (
        <div
          style={{
            padding: bigScreenMode ? '10px 12px' : '8px 10px',
            borderTop: '1px solid var(--border)',
            background: 'var(--bg-primary)',
          }}
        >
          {/* 动作 */}
          {step.action && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <ToolOutlined style={{ color: 'var(--accent-blue)' }} />
                <Text
                  style={{
                    color: 'var(--accent-blue)',
                    fontSize: bigScreenMode ? 12 : 10,
                    fontWeight: 500,
                  }}
                >
                  Action: {step.action}
                </Text>
                <span style={{ fontSize: bigScreenMode ? 14 : 12 }}>{actionIcon}</span>
              </div>
              {step.action_input && Object.keys(step.action_input).length > 0 && (
                <div
                  style={{
                    background: 'var(--bg-card)',
                    padding: '6px 10px',
                    borderRadius: 4,
                    fontSize: bigScreenMode ? 11 : 9,
                    fontFamily: 'monospace',
                    color: 'var(--text-secondary)',
                    marginLeft: 20,
                  }}
                >
                  {JSON.stringify(step.action_input, null, 2)}
                </div>
              )}
            </div>
          )}

          {/* 观察结果 */}
          {step.observation && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <EyeOutlined style={{ color: 'var(--accent-green)' }} />
                <Text
                  style={{
                    color: 'var(--accent-green)',
                    fontSize: bigScreenMode ? 12 : 10,
                    fontWeight: 500,
                  }}
                >
                  Observation
                </Text>
              </div>
              <div
                style={{
                  background: 'var(--bg-card)',
                  padding: '6px 10px',
                  borderRadius: 4,
                  fontSize: bigScreenMode ? 11 : 9,
                  fontFamily: 'monospace',
                  color: 'var(--text-secondary)',
                  marginLeft: 20,
                  maxHeight: 200,
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {step.observation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ReasoningTrace() {
  const { currentToolCalls, actions, reasoningSteps } = useSessionStore();
  const { bigScreenMode, showReasoningTrace, toggleReasoningTrace } = useUIStore();
  const [showMode, setShowMode] = useState<'reasoning' | 'tools'>('reasoning');

  // 合并当前工具调用和历史动作
  const allToolCalls = currentToolCalls.length > 0
    ? currentToolCalls
    : actions.map((action, index) => ({
        id: `action-${index}`,
        tool_name: action.action,
        status: action.status === 'completed' ? 'completed' : 'pending' as ToolStatus,
        start_time: action.time || '',
        output: action.description || '',
      }));

  const totalCount = reasoningSteps.length + allToolCalls.length;

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        marginTop: bigScreenMode ? 12 : 8,
      }}
    >
      {/* 标题栏 */}
      <div
        onClick={toggleReasoningTrace}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: bigScreenMode ? '10px 12px' : '8px 10px',
          cursor: 'pointer',
          borderBottom: showReasoningTrace ? '1px solid var(--border)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: bigScreenMode ? 16 : 14 }}>🧠</span>
          <Text
            style={{
              color: 'var(--text-primary)',
              fontSize: bigScreenMode ? 14 : 12,
              fontWeight: 500,
            }}
          >
            推理轨迹
          </Text>
          {totalCount > 0 && (
            <span
              style={{
                background: 'var(--accent-blue)',
                color: '#fff',
                fontSize: bigScreenMode ? 11 : 9,
                padding: '1px 6px',
                borderRadius: 10,
              }}
            >
              {totalCount}
            </span>
          )}
        </div>
        {showReasoningTrace ? (
          <DownOutlined style={{ fontSize: 12, color: 'var(--text-secondary)' }} />
        ) : (
          <RightOutlined style={{ fontSize: 12, color: 'var(--text-secondary)' }} />
        )}
      </div>

      {/* 内容区域 */}
      {showReasoningTrace && (
        <div>
          {/* 切换标签 */}
          {(reasoningSteps.length > 0 || allToolCalls.length > 0) && (
            <div
              style={{
                display: 'flex',
                gap: 4,
                padding: bigScreenMode ? '8px 12px' : '6px 8px',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMode('reasoning');
                }}
                style={{
                  padding: '4px 12px',
                  fontSize: bigScreenMode ? 12 : 10,
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  background: showMode === 'reasoning' ? 'var(--accent-blue)' : 'transparent',
                  color: showMode === 'reasoning' ? '#fff' : 'var(--text-secondary)',
                }}
              >
                推理步骤 ({reasoningSteps.length})
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMode('tools');
                }}
                style={{
                  padding: '4px 12px',
                  fontSize: bigScreenMode ? 12 : 10,
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  background: showMode === 'tools' ? 'var(--accent-blue)' : 'transparent',
                  color: showMode === 'tools' ? '#fff' : 'var(--text-secondary)',
                }}
              >
                工具调用 ({allToolCalls.length})
              </button>
            </div>
          )}

          {/* 推理步骤列表 */}
          {showMode === 'reasoning' && (
            <div
              style={{
                padding: bigScreenMode ? '12px' : '8px',
                maxHeight: 400,
                overflowY: 'auto',
              }}
            >
              {reasoningSteps.length === 0 ? (
                <Text
                  style={{
                    color: 'var(--text-secondary)',
                    fontSize: bigScreenMode ? 12 : 10,
                  }}
                >
                  暂无推理步骤
                </Text>
              ) : (
                reasoningSteps.map((step, index) => (
                  <ReasoningStepItem key={index} step={step} bigScreenMode={bigScreenMode} />
                ))
              )}
            </div>
          )}

          {/* 工具调用列表 */}
          {showMode === 'tools' && (
            <div
              style={{
                padding: bigScreenMode ? '12px' : '8px',
                maxHeight: 400,
                overflowY: 'auto',
              }}
            >
              {allToolCalls.length === 0 ? (
                <Text
                  style={{
                    color: 'var(--text-secondary)',
                    fontSize: bigScreenMode ? 12 : 10,
                  }}
                >
                  暂无工具调用
                </Text>
              ) : (
                allToolCalls.map((tc) => (
                  <ToolCallItem key={tc.id} toolCall={tc} bigScreenMode={bigScreenMode} />
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
