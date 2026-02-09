import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';
import type { FSMStateDefinition } from '../../types';

type DisplayState = { id: string; label: string; short: string };

// FSM 状态定义（默认兜底）
const defaultFsmStates: DisplayState[] = [
  { id: 'INIT', label: '初始化', short: '初始' },
  { id: 'P1_RISK_ASSESS', label: '风险评估', short: 'P1' },
  { id: 'P2_IMMEDIATE_CONTROL', label: '即时控制', short: 'P2' },
  { id: 'P3_RESOURCE_DISPATCH', label: '资源调度', short: 'P3' },
  { id: 'P4_AREA_ISOLATION', label: '区域隔离', short: 'P4' },
  { id: 'P5_CLEANUP', label: '现场处置', short: 'P5' },
  { id: 'P6_VERIFICATION', label: '结果确认', short: 'P6' },
  { id: 'P7_RECOVERY', label: '运行恢复', short: 'P7' },
  { id: 'P8_CLOSE', label: '关闭', short: 'P8' },
  { id: 'COMPLETED', label: '完成', short: '完成' },
];

// 状态名称映射（处理后端不同命名格式）
const stateMapping: Record<string, string> = {
  // 缩写形式
  'P1_RISK': 'P1_RISK_ASSESS',
  'P2_CONTROL': 'P2_IMMEDIATE_CONTROL',
  'P3_RESOURCE': 'P3_RESOURCE_DISPATCH',
  'P4_AREA': 'P4_AREA_ISOLATION',
  'P5_CLEAN': 'P5_CLEANUP',
  'P6_VERIFY': 'P6_VERIFICATION',
  'P7_RECOVERY': 'P7_RECOVERY',
  'P8_CLOSE': 'P8_CLOSE',
  // 下划线变体
  'RISK_ASSESS': 'P1_RISK_ASSESS',
  'IMMEDIATE_CONTROL': 'P2_IMMEDIATE_CONTROL',
  'RESOURCE_DISPATCH': 'P3_RESOURCE_DISPATCH',
  'AREA_ISOLATION': 'P4_AREA_ISOLATION',
  'CLEANUP': 'P5_CLEANUP',
  'VERIFICATION': 'P6_VERIFICATION',
  'RECOVERY': 'P7_RECOVERY',
  'CLOSE': 'P8_CLOSE',
  'COMPLETE': 'COMPLETED',
  // 兼容历史命名（旧版前端/演示数据）
  'P3_IMPACT_ANALYSIS': 'P4_AREA_ISOLATION',
  'P4_NOTIFICATION': 'P2_IMMEDIATE_CONTROL',
  'P5_MONITORING': 'P5_CLEANUP',
  'P6_FOLLOWUP': 'P7_RECOVERY',
  'P7_REPORTING': 'P8_CLOSE',
  'IMPACT_ANALYSIS': 'P4_AREA_ISOLATION',
  'NOTIFICATION': 'P2_IMMEDIATE_CONTROL',
  'MONITORING': 'P5_CLEANUP',
  'FOLLOWUP': 'P7_RECOVERY',
  'REPORTING': 'P8_CLOSE',
};

function getShortLabel(id: string, label: string): string {
  if (id === 'INIT') return '初始';
  if (id === 'COMPLETED') return '完成';
  const match = id.match(/^P(\d+)/);
  if (match) return `P${match[1]}`;
  if (label) return label.slice(0, 2);
  return id.slice(0, 3);
}

function buildDisplayStates(fsmStates: FSMStateDefinition[]): DisplayState[] {
  const sorted = [...fsmStates].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  return sorted.map((state) => ({
    id: state.id,
    label: state.name,
    short: getShortLabel(state.id, state.name),
  }));
}

// 规范化状态名称
function normalizeState(state: string, availableStates: DisplayState[]): string {
  if (availableStates.find((s) => s.id === state)) {
    return state;
  }
  const mapped = stateMapping[state.toUpperCase()];
  if (mapped && availableStates.find((s) => s.id === mapped)) {
    return mapped;
  }
  const upper = state.toUpperCase();
  const exact = availableStates.find((s) => s.id.toUpperCase() === upper);
  if (exact) return exact.id;
  for (const [key, value] of Object.entries(stateMapping)) {
    if ((upper.includes(key) || key.includes(upper)) && availableStates.find((s) => s.id === value)) {
      return value;
    }
  }
  return availableStates[0]?.id || 'INIT';
}

// 获取状态索引
function getStateIndex(state: string, availableStates: DisplayState[]): number {
  const normalized = normalizeState(state, availableStates);
  const index = availableStates.findIndex((s) => s.id === normalized);
  return index >= 0 ? index : 0;
}

export function FSMFlow() {
  const { fsmState, incident, fsmStates: scenarioStates } = useSessionStore();
  const { bigScreenMode } = useUIStore();

  const displayStates =
    scenarioStates && scenarioStates.length > 0
      ? buildDisplayStates(scenarioStates)
      : defaultFsmStates;
  const currentIndex = getStateIndex(fsmState, displayStates);
  const scenarioLabel = incident?.scenario_type
    ? {
        oil_spill: '油污泄漏',
        bird_strike: '鸟击事件',
        fod: 'FOD 外来物',
        tire_burst: '轮胎爆破',
        runway_incursion: '跑道入侵',
      }[incident.scenario_type] || incident.scenario_type
    : '待识别';

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: bigScreenMode ? '16px' : '8px',
      }}
    >
      {/* 状态流程图 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: bigScreenMode ? 8 : 4,
        }}
      >
        {displayStates.map((state, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <div
              key={state.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                flex: 1,
                minWidth: 0,
              }}
            >
              {/* 状态节点 */}
              <div
                className={isCurrent ? 'pulse-glow' : ''}
                style={{
                  width: bigScreenMode ? 36 : 28,
                  height: bigScreenMode ? 36 : 28,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: bigScreenMode ? 11 : 9,
                  fontWeight: 600,
                  transition: 'all 0.3s ease',
                  flexShrink: 0,
                  background: isCompleted
                    ? 'var(--accent-green)'
                    : isCurrent
                    ? 'var(--accent-blue)'
                    : 'var(--bg-primary)',
                  border: `2px solid ${
                    isCompleted
                      ? 'var(--accent-green)'
                      : isCurrent
                      ? 'var(--accent-blue)'
                      : 'var(--border)'
                  }`,
                  color: isCompleted || isCurrent ? '#fff' : 'var(--text-secondary)',
                  boxShadow: isCurrent
                    ? '0 0 15px rgba(31, 111, 235, 0.6)'
                    : 'none',
                }}
                title={state.label}
              >
                {state.short}
              </div>

              {/* 连接线 */}
              {index < displayStates.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: 2,
                    minWidth: 8,
                    background: isCompleted
                      ? 'var(--accent-green)'
                      : 'var(--border)',
                    margin: '0 2px',
                    transition: 'background 0.3s ease',
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* 当前状态说明 */}
      <div
        style={{
          marginTop: bigScreenMode ? 16 : 12,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            color: 'var(--text-secondary)',
            fontSize: bigScreenMode ? 12 : 10,
            marginBottom: 6,
          }}
        >
          场景: {scenarioLabel}
        </div>
        <span
          style={{
            color: 'var(--accent-blue)',
            fontSize: bigScreenMode ? 14 : 12,
            fontWeight: 500,
          }}
        >
          当前阶段: {displayStates[currentIndex]?.label || 'N/A'}
        </span>
        {currentIndex > 0 && (
          <span
            style={{
              color: 'var(--text-secondary)',
              fontSize: bigScreenMode ? 12 : 10,
              marginLeft: 12,
            }}
          >
            已完成: {currentIndex}/{displayStates.length}
          </span>
        )}
      </div>
    </div>
  );
}
