import { Component, useEffect, useRef, useState } from 'react';
import { Typography, Button } from 'antd';
import {
  UserOutlined,
  RobotOutlined,
  InfoCircleOutlined,
  BulbOutlined,
  ToolOutlined,
  EyeOutlined,
  DownOutlined,
  RightOutlined,
  FileTextOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';
import type { Message, ReasoningStep } from '../../types';
import ReactMarkdown from 'react-markdown';

const { Text } = Typography;

// 错误边界组件 - 防止子组件崩溃导致整个界面消失
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ChatErrorBoundary extends Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ChatTimeline Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: 16,
            color: 'var(--danger)',
            background: 'rgba(248, 81, 73, 0.1)',
            borderRadius: 8,
            margin: 12,
          }}
        >
          <WarningOutlined style={{ marginRight: 8 }} />
          渲染出错: {this.state.error?.message || '未知错误'}
          <Button
            size="small"
            style={{ marginLeft: 12 }}
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            重试
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

interface MessageBubbleProps {
  message: Message;
  bigScreenMode: boolean;
}

// 系统消息气泡
function SystemMessageBubble({ message, bigScreenMode }: MessageBubbleProps) {
  // 解析系统消息类型
  const isScenarioMessage = message.content.includes('[信息] 识别场景');
  const isExtractionMessage = message.content.includes('[信息] 本次提取') || message.content.includes('[信息] 已收集信息');
  const isFlightPlanMessage = message.content.includes('[信息] 航班计划');

  let icon = <InfoCircleOutlined style={{ fontSize: bigScreenMode ? 14 : 12 }} />;
  let bgColor = 'rgba(139, 148, 158, 0.15)';
  let textColor = '#8b949e';

  if (isScenarioMessage) {
    icon = <span style={{ fontSize: bigScreenMode ? 14 : 12 }}>🎯</span>;
    bgColor = 'rgba(31, 111, 235, 0.1)';
    textColor = 'var(--accent-blue)';
  } else if (isExtractionMessage) {
    icon = <span style={{ fontSize: bigScreenMode ? 14 : 12 }}>📝</span>;
    bgColor = 'rgba(35, 134, 54, 0.1)';
    textColor = 'var(--accent-green)';
  } else if (isFlightPlanMessage) {
    icon = <span style={{ fontSize: bigScreenMode ? 14 : 12 }}>✈️</span>;
    bgColor = 'rgba(88, 166, 255, 0.1)';
    textColor = '#58a6ff';
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        marginBottom: bigScreenMode ? 8 : 6,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          padding: bigScreenMode ? '8px 14px' : '6px 12px',
          background: bgColor,
          borderRadius: 6,
          maxWidth: '95%',
          border: `1px solid ${textColor}20`,
        }}
      >
        <div style={{ paddingTop: 2 }}>{icon}</div>
        <Text
          style={{
            color: textColor,
            fontSize: bigScreenMode ? 12 : 11,
            fontFamily: 'JetBrains Mono, Consolas, monospace',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
          }}
        >
          {message.content}
        </Text>
      </div>
    </div>
  );
}

// 安全的 JSON 字符串化
function safeStringify(obj: unknown): string {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
}

// 推理步骤实时显示组件
function ReasoningStepBubble({ step, bigScreenMode }: { step: ReasoningStep; bigScreenMode: boolean }) {
  const [expanded, setExpanded] = useState(false);

  const summary = step?.action
    ? `调用工具: ${step.action}`
    : step?.observation
      ? '处理工具反馈'
      : '推理更新';
  const action = step?.action || '';
  const actionInput = step?.action_input;
  const observation = step?.observation || '';

  // 如果 step 为空，渲染空占位
  if (!step) {
    return null;
  }

  return (
    <div
      style={{
        marginBottom: bigScreenMode ? 10 : 8,
        background: 'var(--bg-primary)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        overflow: 'hidden',
      }}
    >
      {/* 摘要部分 - 始终显示 */}
      <div
        style={{
          padding: bigScreenMode ? '10px 12px' : '8px 10px',
          background: 'rgba(251, 211, 141, 0.1)',
          borderBottom: (action || observation) ? '1px solid var(--border)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
          <BulbOutlined style={{ color: '#fbd38d', marginTop: 2, fontSize: bigScreenMode ? 14 : 12 }} />
          <Text
            style={{
              flex: 1,
              color: 'var(--text-primary)',
              fontSize: bigScreenMode ? 12 : 11,
              lineHeight: 1.6,
              fontFamily: 'system-ui, -apple-system, sans-serif',
            }}
          >
            <strong style={{ color: '#fbd38d' }}>[摘要]</strong> {summary}
          </Text>
        </div>
      </div>

      {/* 执行和观察 - 可折叠 */}
      {(action || observation) && (
        <div>
          <div
            onClick={() => setExpanded(!expanded)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: bigScreenMode ? '6px 12px' : '5px 10px',
              cursor: 'pointer',
              background: 'var(--bg-card)',
            }}
          >
            {expanded ? (
              <DownOutlined style={{ fontSize: 10, color: 'var(--text-secondary)' }} />
            ) : (
              <RightOutlined style={{ fontSize: 10, color: 'var(--text-secondary)' }} />
            )}
            <Text style={{ fontSize: bigScreenMode ? 11 : 10, color: 'var(--text-secondary)' }}>
              {expanded ? '收起详情' : '展开执行和观察'}
            </Text>
          </div>

          {expanded && (
            <div style={{ padding: bigScreenMode ? '10px 12px' : '8px 10px', background: 'var(--bg-primary)' }}>
              {/* 执行部分 */}
              {action && (
                <div style={{ marginBottom: observation ? 10 : 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <ToolOutlined style={{ color: 'var(--accent-blue)', fontSize: bigScreenMode ? 12 : 11 }} />
                    <Text
                      style={{
                        color: 'var(--accent-blue)',
                        fontSize: bigScreenMode ? 11 : 10,
                        fontWeight: 600,
                      }}
                    >
                      [执行] {action}
                    </Text>
                  </div>
                  {actionInput && typeof actionInput === 'object' && Object.keys(actionInput).length > 0 && (
                    <div
                      style={{
                        background: 'var(--bg-card)',
                        padding: '6px 10px',
                        borderRadius: 4,
                        fontSize: bigScreenMode ? 10 : 9,
                        fontFamily: 'JetBrains Mono, monospace',
                        color: 'var(--text-secondary)',
                        marginLeft: 18,
                      }}
                    >
                      {safeStringify(actionInput)}
                    </div>
                  )}
                </div>
              )}

              {/* 观察部分 */}
              {observation && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <EyeOutlined style={{ color: 'var(--accent-green)', fontSize: bigScreenMode ? 12 : 11 }} />
                    <Text
                      style={{
                        color: 'var(--accent-green)',
                        fontSize: bigScreenMode ? 11 : 10,
                        fontWeight: 600,
                      }}
                    >
                      [观察]
                    </Text>
                  </div>
                  <div
                    style={{
                      background: 'var(--bg-card)',
                      padding: '6px 10px',
                      borderRadius: 4,
                      fontSize: bigScreenMode ? 11 : 10,
                      fontFamily: 'JetBrains Mono, monospace',
                      color: 'var(--text-secondary)',
                      marginLeft: 18,
                      maxHeight: 200,
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {observation}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// 检测是否为工单内容
function isReportContent(content: string): boolean {
  return (
    content.includes('## 机坪特情处置检查单') ||
    content.includes('# 机坪特情处置检查单') ||
    (content.includes('基本信息') && content.includes('风险评估') && content.includes('处置建议'))
  );
}

// 提取工单摘要
function extractReportSummary(content: string): string {
  const lines = content.split('\n');
  const summary: string[] = [];

  for (const line of lines) {
    if (line.includes('航班号') || line.includes('位置') || line.includes('风险等级') || line.includes('油液类型')) {
      summary.push(line);
    }
    if (summary.length >= 6) break;
  }

  return summary.length > 0 ? summary.join('\n') : '工单已生成，包含基本信息、风险评估和处置建议';
}

// 用户/助手消息气泡（带有 hooks）
function UserAssistantBubble({ message, bigScreenMode }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const [showFullReport, setShowFullReport] = useState(false);

  // 检测是否为工单内容
  const isReport = !isUser && isReportContent(message.content);
  const reportSummary = isReport ? extractReportSummary(message.content) : '';

  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        marginBottom: bigScreenMode ? 16 : 12,
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      {/* 头像 */}
      <div
        style={{
          width: bigScreenMode ? 36 : 28,
          height: bigScreenMode ? 36 : 28,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          background: isUser ? 'var(--accent-blue)' : 'var(--accent-green)',
        }}
      >
        {isUser ? (
          <UserOutlined style={{ color: '#fff', fontSize: bigScreenMode ? 18 : 14 }} />
        ) : (
          <RobotOutlined style={{ color: '#fff', fontSize: bigScreenMode ? 18 : 14 }} />
        )}
      </div>

      {/* 消息内容 */}
      <div
        style={{
          flex: 1,
          maxWidth: '85%',
        }}
      >
        {/* 时间戳 */}
        <Text
          style={{
            color: 'var(--text-secondary)',
            fontSize: bigScreenMode ? 12 : 10,
            display: 'block',
            marginBottom: 4,
            textAlign: isUser ? 'right' : 'left',
          }}
        >
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })}
        </Text>

        {/* 消息气泡 */}
        <div
          style={{
            background: isUser ? 'var(--accent-blue)' : 'var(--bg-card)',
            border: isUser ? 'none' : '1px solid var(--border)',
            borderRadius: 8,
            padding: bigScreenMode ? '12px 16px' : '8px 12px',
            color: isUser ? '#fff' : 'var(--text-primary)',
            fontSize: bigScreenMode ? 14 : 13,
            lineHeight: 1.6,
          }}
        >
          {isUser ? (
            message.content
          ) : isReport ? (
            // 工单摘要显示
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <FileTextOutlined style={{ fontSize: bigScreenMode ? 16 : 14, color: 'var(--accent-green)' }} />
                <Text style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: bigScreenMode ? 14 : 13 }}>
                  ✅ 已生成工单模版
                </Text>
              </div>

              {!showFullReport && (
                <>
                  <div
                    style={{
                      padding: '10px 12px',
                      background: 'rgba(35, 134, 54, 0.1)',
                      borderRadius: 6,
                      marginBottom: 10,
                      fontSize: bigScreenMode ? 12 : 11,
                      fontFamily: 'JetBrains Mono, monospace',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.8,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {reportSummary}
                  </div>
                  <Button
                    type="link"
                    size="small"
                    onClick={() => setShowFullReport(true)}
                    style={{ padding: 0, height: 'auto', fontSize: bigScreenMode ? 12 : 11 }}
                  >
                    查看完整工单 →
                  </Button>
                </>
              )}

              {showFullReport && (
                <>
                  <div
                    style={{
                      maxHeight: 400,
                      overflowY: 'auto',
                      padding: '10px',
                      background: 'var(--bg-primary)',
                      borderRadius: 6,
                      marginBottom: 10,
                    }}
                    className="markdown-content"
                  >
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                  <Button
                    type="link"
                    size="small"
                    onClick={() => setShowFullReport(false)}
                    style={{ padding: 0, height: 'auto', fontSize: bigScreenMode ? 12 : 11 }}
                  >
                    收起工单 ↑
                  </Button>
                </>
              )}
            </div>
          ) : (
            // 普通消息
            <div className="markdown-content">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// 消息气泡分发器 - 根据消息类型选择合适的组件
function MessageBubble({ message, bigScreenMode }: MessageBubbleProps) {
  // 系统消息使用无 hooks 的组件
  if (message.role === 'system') {
    return <SystemMessageBubble message={message} bigScreenMode={bigScreenMode} />;
  }
  // 用户/助手消息使用带 hooks 的组件
  return <UserAssistantBubble message={message} bigScreenMode={bigScreenMode} />;
}

export function ChatTimeline() {
  const { messages, isThinking, currentThinking, reasoningSteps } = useSessionStore();
  const { bigScreenMode } = useUIStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isThinking, reasoningSteps]);

  return (
    <ChatErrorBoundary>
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: bigScreenMode ? '16px' : '12px',
        }}
      >
        {messages.length === 0 && reasoningSteps.length === 0 ? (
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
          选择预设场景或输入事件描述开始对话
        </div>
      ) : (
        <>
          {/* 渲染消息 */}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} bigScreenMode={bigScreenMode} />
          ))}

          {/* 渲染推理步骤（在所有消息之后）*/}
          {reasoningSteps.length > 0 && (
            <div style={{ marginTop: bigScreenMode ? 12 : 8, marginBottom: bigScreenMode ? 16 : 12 }}>
              {reasoningSteps.map((step, stepIdx) => (
                <ReasoningStepBubble
                  key={`step-${stepIdx}`}
                  step={step}
                  bigScreenMode={bigScreenMode}
                />
              ))}
            </div>
          )}

          {/* 思考中状态 */}
          {isThinking && (
            <div
              style={{
                display: 'flex',
                gap: 12,
                marginBottom: bigScreenMode ? 16 : 12,
              }}
            >
              <div
                style={{
                  width: bigScreenMode ? 36 : 28,
                  height: bigScreenMode ? 36 : 28,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  background: 'var(--accent-green)',
                }}
              >
                <RobotOutlined style={{ color: '#fff', fontSize: bigScreenMode ? 18 : 14 }} />
              </div>
              <div
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: bigScreenMode ? '12px 16px' : '8px 12px',
                }}
              >
                <span
                  className="typing-cursor"
                  style={{
                    color: 'var(--accent-green)',
                    fontSize: bigScreenMode ? 14 : 13,
                  }}
                >
                  💭 {currentThinking || '正在思考'}
                </span>
              </div>
            </div>
          )}
        </>
      )}
      </div>
    </ChatErrorBoundary>
  );
}
