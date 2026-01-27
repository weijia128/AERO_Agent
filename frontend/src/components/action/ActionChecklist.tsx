import { Checkbox, Tag, Typography } from 'antd';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';
import type { ChecklistItem } from '../../types';

const { Text } = Typography;

// 阶段配置
const phaseConfig: Record<string, { label: string; color: string }> = {
  P1: { label: '信息收集', color: 'var(--accent-blue)' },
  P2: { label: '即时响应', color: 'var(--danger)' },
  P3: { label: '后续处理', color: 'var(--warning)' },
};

interface ChecklistGroupProps {
  phase: string;
  items: ChecklistItem[];
  bigScreenMode: boolean;
}

function ChecklistGroup({ phase, items, bigScreenMode }: ChecklistGroupProps) {
  const config = phaseConfig[phase] || { label: phase, color: 'var(--text-secondary)' };
  const completedCount = items.filter((item) => item.completed).length;

  return (
    <div style={{ marginBottom: bigScreenMode ? 12 : 8 }}>
      {/* 阶段标题 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Tag
            style={{
              background: config.color,
              borderColor: config.color,
              color: '#fff',
              fontSize: bigScreenMode ? 12 : 10,
              padding: '0 6px',
            }}
          >
            {phase}
          </Tag>
          <Text
            style={{
              color: 'var(--text-primary)',
              fontSize: bigScreenMode ? 13 : 11,
              fontWeight: 500,
            }}
          >
            {config.label}
          </Text>
        </div>
        <Text
          style={{
            color: 'var(--text-secondary)',
            fontSize: bigScreenMode ? 12 : 10,
          }}
        >
          {completedCount}/{items.length}
        </Text>
      </div>

      {/* 检查项列表 */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}
      >
        {items.map((item) => (
          <div
            key={item.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: bigScreenMode ? '8px 10px' : '6px 8px',
              background: item.completed
                ? 'rgba(35, 134, 54, 0.1)'
                : 'var(--bg-primary)',
              borderRadius: 4,
              borderLeft: `3px solid ${
                item.completed ? 'var(--accent-green)' : 'var(--border)'
              }`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Checkbox
                checked={item.completed}
                disabled
                style={{
                  transform: bigScreenMode ? 'scale(1.1)' : 'scale(1)',
                }}
              />
              <Text
                style={{
                  color: item.completed
                    ? 'var(--text-secondary)'
                    : 'var(--text-primary)',
                  fontSize: bigScreenMode ? 13 : 11,
                  textDecoration: item.completed ? 'line-through' : 'none',
                }}
              >
                {item.item}
              </Text>
            </div>
            {item.department && (
              <Tag
                style={{
                  fontSize: bigScreenMode ? 10 : 8,
                  padding: '0 4px',
                  background: 'var(--bg-card)',
                  borderColor: 'var(--border)',
                  color: 'var(--text-secondary)',
                }}
              >
                {item.department}
              </Tag>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ActionChecklist() {
  const { checklist } = useSessionStore();
  const { bigScreenMode } = useUIStore();

  // 按阶段分组
  const groupedItems = checklist.reduce<Record<string, ChecklistItem[]>>(
    (acc, item) => {
      if (!acc[item.phase]) {
        acc[item.phase] = [];
      }
      acc[item.phase].push(item);
      return acc;
    },
    {}
  );

  if (checklist.length === 0) {
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
        等待处置清单...
      </div>
    );
  }

  const totalCompleted = checklist.filter((item) => item.completed).length;

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 总进度 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: bigScreenMode ? 12 : 8,
          padding: bigScreenMode ? '8px 12px' : '6px 10px',
          background: 'var(--bg-primary)',
          borderRadius: 6,
        }}
      >
        <Text
          style={{
            color: 'var(--text-secondary)',
            fontSize: bigScreenMode ? 13 : 11,
          }}
        >
          处置进度
        </Text>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 100,
              height: 6,
              background: 'var(--border)',
              borderRadius: 3,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${(totalCompleted / checklist.length) * 100}%`,
                height: '100%',
                background: 'var(--accent-green)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
          <Text
            style={{
              color: 'var(--accent-green)',
              fontSize: bigScreenMode ? 13 : 11,
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            {totalCompleted}/{checklist.length}
          </Text>
        </div>
      </div>

      {/* 分组列表 */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
        }}
      >
        {Object.entries(groupedItems).map(([phase, items]) => (
          <ChecklistGroup
            key={phase}
            phase={phase}
            items={items}
            bigScreenMode={bigScreenMode}
          />
        ))}
      </div>
    </div>
  );
}
