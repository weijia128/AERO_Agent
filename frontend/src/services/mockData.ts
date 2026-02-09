import type {
  SessionState,
  Message,
  ToolCall,
  ChecklistItem,
  PresetScenario,
  Weather,
  TopologyNode,
  AffectedFlight,
  SpreadStep,
} from '../types';
import samplesData from '../../../oil_spill_test_samples.json';

type OilSpillSample = {
  id: number;
  description: string;
  input_text: string;
  expected_risk_level: 'R1' | 'R2' | 'R3' | 'R4';
  expected_score: number;
  key_factors: {
    fluid_type?: 'FUEL' | 'HYDRAULIC' | 'OIL' | string;
    continuous?: boolean;
    engine_status?: 'RUNNING' | 'STOPPED' | string;
    leak_size?: 'LARGE' | 'SMALL' | string;
    position?: string;
    flight_callsign?: string;
    airline?: string;
  };
};

type OilSpillSamplesFile = {
  test_samples?: OilSpillSample[];
};

const samples = ((samplesData as OilSpillSamplesFile).test_samples || []).filter(Boolean);

const fallbackSample: OilSpillSample = {
  id: 0,
  description: '默认样本：滑油泄漏',
  input_text: '示例航班报告滑油泄漏，发动机已关闭，请求支援。',
  expected_risk_level: 'R2',
  expected_score: 30,
  key_factors: {
    fluid_type: 'OIL',
    continuous: false,
    engine_status: 'STOPPED',
    position: '217',
    flight_callsign: 'CES2146',
    airline: 'CES',
  },
};

const defaultSample = samples.find((sample) => sample.id === 9) || samples[0] || fallbackSample;

const fluidLabels: Record<string, string> = {
  FUEL: '燃油',
  HYDRAULIC: '液压油',
  OIL: '滑油',
};

const engineLabels: Record<string, string> = {
  RUNNING: '运转中',
  STOPPED: '已关闭',
};

const leakSizeLabels: Record<string, string> = {
  LARGE: '较大',
  SMALL: '较小',
};

const riskSeverityMap: Record<string, AffectedFlight['severity']> = {
  R4: 'severe',
  R3: 'moderate',
  R2: 'minor',
  R1: 'minor',
};

const riskDelayMap: Record<string, number> = {
  R4: 60,
  R3: 30,
  R2: 20,
  R1: 10,
};

const aircraftTypes = ['A320', 'B738', 'A321', 'B737', 'A319', 'B787'];

function normalizePosition(value?: string): string {
  if (!value) return '';
  return value
    .replace(/(滑行道|跑道|机位|停机位|机坪)/g, '')
    .replace(/\s+/g, '')
    .toUpperCase();
}

function inferPositionType(value?: string): 'stand' | 'taxiway' | 'runway' | 'unknown' {
  const normalized = normalizePosition(value);
  if (!normalized) return 'unknown';
  if (normalized.includes('/')) return 'runway';
  if (/^\d{1,2}[LRC]?$/.test(normalized)) return 'runway';
  if (/^\d{2,3}$/.test(normalized)) return 'stand';
  if (/^[A-Z]+\d*$/.test(normalized)) return 'taxiway';
  return 'unknown';
}

function formatPosition(value?: string): string {
  if (!value) return '未知位置';
  const normalized = normalizePosition(value);
  const positionType = inferPositionType(value);
  if (positionType === 'stand') return `${normalized}机位`;
  if (positionType === 'taxiway') return `滑行道${normalized}`;
  if (positionType === 'runway') return `跑道${normalized}`;
  return value;
}

function buildPresetScenarios(sampleList: OilSpillSample[]): PresetScenario[] {
  const pickByRisk = (level: OilSpillSample['expected_risk_level']) =>
    sampleList.find((sample) => sample.expected_risk_level === level);

  const selectedSamples = [
    pickByRisk('R4'),
    pickByRisk('R3'),
    pickByRisk('R1'),
  ].filter(Boolean) as OilSpillSample[];

  const fallbackSamples = selectedSamples.length > 0 ? selectedSamples : sampleList.slice(0, 3);

  return fallbackSamples.map((sample, index) => ({
    id: `oil-spill-sample-${sample.id || index + 1}`,
    name: `漏油样本 ${sample.id || index + 1}`,
    description: sample.description,
    initial_message: sample.input_text,
    expected_risk_level: sample.expected_risk_level,
    scenario_type: 'oil_spill',
  }));
}

function buildAffectedFlights(sampleList: OilSpillSample[]): AffectedFlight[] {
  const baseDate = '2025-10-21';
  const baseMinutes = 12 * 60;

  return sampleList.slice(0, 7).map((sample, index) => {
    const minutes = baseMinutes + index * 5;
    const hours = String(Math.floor(minutes / 60)).padStart(2, '0');
    const mins = String(minutes % 60).padStart(2, '0');
    const scheduled_time = `${baseDate} ${hours}:${mins}:00`;

    const positionType = inferPositionType(sample.key_factors.position);
    const normalizedPosition = normalizePosition(sample.key_factors.position);
    const standLabel = positionType === 'stand' ? normalizedPosition : formatPosition(sample.key_factors.position);

    const riskLevel = sample.expected_risk_level || 'R3';

    return {
      callsign: sample.key_factors.flight_callsign || `DEMO${index + 1}`,
      aircraft_type: aircraftTypes[index % aircraftTypes.length],
      stand: standLabel,
      runway: positionType === 'runway' ? normalizedPosition : undefined,
      scheduled_time,
      delay: riskDelayMap[riskLevel] + index * 2,
      severity: riskSeverityMap[riskLevel],
    };
  });
}

function buildSpatialAnalysis(sample: OilSpillSample): {
  affected_stands: string[];
  affected_taxiways: string[];
  affected_runways: string[];
  impact_radius: number;
  spread_animation: SpreadStep[];
} {
  const normalizedPosition = normalizePosition(sample.key_factors.position);
  const positionType = inferPositionType(sample.key_factors.position);

  let affected_stands: string[] = [];
  let affected_taxiways: string[] = [];
  let affected_runways: string[] = [];

  if (positionType === 'stand' && /^\d+$/.test(normalizedPosition)) {
    const base = parseInt(normalizedPosition, 10);
    const neighbors = [base - 1, base + 1].filter((value) => value > 0).map((value) => String(value));
    affected_stands = [String(base), ...neighbors];
  } else if (positionType === 'taxiway') {
    affected_taxiways = [normalizedPosition];
  } else if (positionType === 'runway') {
    affected_runways = [normalizedPosition];
  }

  const spread_animation: SpreadStep[] = [];
  if (normalizedPosition) {
    spread_animation.push({ time: 0, nodes: [normalizedPosition], color: '#f85149' });
  }
  if (affected_stands.length > 1) {
    spread_animation.push({ time: 1, nodes: affected_stands.slice(1), color: '#d29922' });
  }
  if (affected_taxiways.length > 0) {
    spread_animation.push({ time: 2, nodes: affected_taxiways, color: '#fadb14' });
  }
  if (affected_runways.length > 0) {
    spread_animation.push({ time: 2, nodes: affected_runways, color: '#fadb14' });
  }

  return {
    affected_stands,
    affected_taxiways,
    affected_runways,
    impact_radius: positionType === 'stand' ? 2 : 3,
    spread_animation,
  };
}

function buildRules(sample: OilSpillSample): string[] {
  const rules: string[] = [];
  const fluidLabel = fluidLabels[sample.key_factors.fluid_type || ''] || sample.key_factors.fluid_type || '油液';
  rules.push(`Rule: ${fluidLabel}泄漏`);
  if (sample.key_factors.engine_status === 'RUNNING') {
    rules.push('Rule: 发动机运转');
  }
  if (sample.key_factors.continuous) {
    rules.push('Rule: 持续泄漏');
  }
  if (sample.key_factors.leak_size === 'LARGE') {
    rules.push('Rule: 泄漏面积较大');
  }
  return rules;
}

function summarizeFactors(sample: OilSpillSample): string[] {
  const factors: string[] = [];
  if (sample.key_factors.fluid_type) factors.push(sample.key_factors.fluid_type);
  if (sample.key_factors.engine_status) factors.push(`ENGINE_${sample.key_factors.engine_status}`);
  if (sample.key_factors.continuous) factors.push('CONTINUOUS');
  if (sample.key_factors.leak_size) factors.push(`LEAK_${sample.key_factors.leak_size}`);
  return factors;
}

function buildRiskAssessment(sample: OilSpillSample) {
  return {
    level: sample.expected_risk_level,
    score: sample.expected_score,
    factors: summarizeFactors(sample),
    rules_triggered: buildRules(sample),
    cross_validation: {
      rule_result: sample.expected_risk_level,
      rule_score: sample.expected_score,
      llm_result: sample.expected_risk_level,
      llm_confidence: sample.expected_risk_level === 'R4' ? 0.92 : 0.88,
      consistent: true,
    },
  };
}

const presetScenarioList = buildPresetScenarios(samples.length > 0 ? samples : [defaultSample]);
const affectedFlightsList = buildAffectedFlights(samples.length > 0 ? samples : [defaultSample]);
const spatialAnalysis = buildSpatialAnalysis(defaultSample);
const riskAssessment = buildRiskAssessment(defaultSample);

const defaultFlight = defaultSample.key_factors.flight_callsign || 'DEMO0001';
const positionLabel = formatPosition(defaultSample.key_factors.position);
const fluidLabel = fluidLabels[defaultSample.key_factors.fluid_type || ''] || '油液';
const engineLabel = engineLabels[defaultSample.key_factors.engine_status || ''] || '状态未知';
const leakSizeLabel = leakSizeLabels[defaultSample.key_factors.leak_size || ''] || '';

// 预设演示场景（来自 oil_spill_test_samples.json）
export const presetScenarios: PresetScenario[] = presetScenarioList;

// 模拟天气数据（天府机场）
export const mockWeather: Weather = {
  timestamp: '2025-10-21T12:00:00',
  location_id: 'ZUTF',
  temperature: 18,
  dew_point: 12,
  relative_humidity: 68,
  visibility: 8000,
  wind_direction: 60,
  wind_speed: 6,
  qnh: 1008,
};

// 模拟拓扑节点（简化版）
export const mockTopologyNodes: TopologyNode[] = [
  { id: '217', name: '217机位', type: 'stand', coordinates: [104.4392, 30.3121], adjacent: ['218', 'L6'], terminal: 'T1', zone: 'A' },
  { id: '218', name: '218机位', type: 'stand', coordinates: [104.4398, 30.3122], adjacent: ['217', '219', 'L6'], terminal: 'T1', zone: 'A' },
  { id: '219', name: '219机位', type: 'stand', coordinates: [104.4404, 30.3122], adjacent: ['218', '221', 'L6'], terminal: 'T1', zone: 'A' },
  { id: '221', name: '221机位', type: 'stand', coordinates: [104.4412, 30.3123], adjacent: ['219', '222', 'L6'], terminal: 'T1', zone: 'A' },
  { id: '222', name: '222机位', type: 'stand', coordinates: [104.4419, 30.3123], adjacent: ['221', '223', 'L6'], terminal: 'T1', zone: 'A' },
  { id: '223', name: '223机位', type: 'stand', coordinates: [104.4426, 30.3124], adjacent: ['222', '224', 'L6'], terminal: 'T1', zone: 'A' },
  { id: '224', name: '224机位', type: 'stand', coordinates: [104.4433, 30.3125], adjacent: ['223', 'L6'], terminal: 'T1', zone: 'A' },
  { id: 'taxiway_L6', name: 'L6滑行道', type: 'taxiway', coordinates: [104.441, 30.3114], adjacent: ['217', '218', '219', '221', '222', '223', '224', 'runway_11_29'] },
  { id: 'runway_11_29', name: '11/29跑道', type: 'runway', coordinates: [104.435, 30.306], adjacent: ['taxiway_L6'] },
  { id: 'fire_station_1', name: '消防站1', type: 'fire_station', coordinates: [104.438, 30.308] },
];

// 模拟受影响航班（来自油污样本航班号）
export const mockAffectedFlights: AffectedFlight[] = affectedFlightsList;

// 模拟检查清单
export const mockChecklist: ChecklistItem[] = [
  { id: 'p1-1', phase: 'P1', item: '确认油液类型', completed: true, department: '机务' },
  { id: 'p1-2', phase: 'P1', item: '确认发动机状态', completed: true, department: '机务' },
  { id: 'p1-3', phase: 'P1', item: '确认泄漏状态', completed: true, department: '机务' },
  { id: 'p1-4', phase: 'P1', item: '风险评估', completed: true, department: '系统' },
  { id: 'p2-1', phase: 'P2', item: '通知消防部门', completed: true, department: '消防', deadline: '立即' },
  { id: 'p2-2', phase: 'P2', item: '通知运行中心', completed: true, department: '运行', deadline: '立即' },
  { id: 'p2-3', phase: 'P2', item: '疏散相邻机位', completed: false, department: '运行', deadline: '5分钟' },
  { id: 'p2-4', phase: 'P2', item: '设置警戒区域', completed: false, department: '安保', deadline: '10分钟' },
  { id: 'p3-1', phase: 'P3', item: '启动清污作业', completed: false, department: '地服', deadline: '15分钟' },
  { id: 'p3-2', phase: 'P3', item: '协调延误航班', completed: false, department: '运行', deadline: '即时' },
];

// 模拟工具调用
export const mockToolCalls: ToolCall[] = [
  {
    id: 'tc-1',
    tool_name: 'get_aircraft_info',
    status: 'completed',
    start_time: '2025-10-21T12:00:01',
    end_time: '2025-10-21T12:00:02',
    input: { flight_no: defaultFlight },
    output: `${defaultFlight}, 计划12:30起飞`,
  },
  {
    id: 'tc-2',
    tool_name: 'get_topology_info',
    status: 'completed',
    start_time: '2025-10-21T12:00:02',
    end_time: '2025-10-21T12:00:03',
    input: { position: defaultSample.key_factors.position || '' },
    output: `${positionLabel}, 已定位至拓扑节点`,
  },
  {
    id: 'tc-3',
    tool_name: 'get_weather',
    status: 'completed',
    start_time: '2025-10-21T12:00:03',
    end_time: '2025-10-21T12:00:04',
    input: { location: 'ZUTF' },
    output: '18°C, 风向060°, 风速6kt, 能见度8000m',
  },
  {
    id: 'tc-4',
    tool_name: 'assess_oil_spill_risk',
    status: 'completed',
    start_time: '2025-10-21T12:00:05',
    end_time: '2025-10-21T12:00:06',
    input: {
      fluid_type: defaultSample.key_factors.fluid_type,
      engine_status: defaultSample.key_factors.engine_status,
      continuous: defaultSample.key_factors.continuous,
    },
    output: `${defaultSample.expected_risk_level} (${defaultSample.expected_score}分) - ${buildRules(defaultSample).join('，')}`,
  },
  {
    id: 'tc-5',
    tool_name: 'notify_department',
    status: 'completed',
    start_time: '2025-10-21T12:00:06',
    end_time: '2025-10-21T12:00:07',
    input: { department: 'fire', priority: 'high' },
    output: '消防部门已通知',
  },
  {
    id: 'tc-6',
    tool_name: 'notify_department',
    status: 'completed',
    start_time: '2025-10-21T12:00:07',
    end_time: '2025-10-21T12:00:08',
    input: { department: 'ops', priority: 'high' },
    output: '运行中心已通知',
  },
  {
    id: 'tc-7',
    tool_name: 'analyze_impact_zone',
    status: 'completed',
    start_time: '2025-10-21T12:00:08',
    end_time: '2025-10-21T12:00:09',
    input: { position: defaultSample.key_factors.position || '', risk_level: defaultSample.expected_risk_level },
    output: `影响范围: ${[
      ...spatialAnalysis.affected_stands,
      ...spatialAnalysis.affected_taxiways,
      ...spatialAnalysis.affected_runways,
    ].join('、') || '待确认'}`,
  },
  {
    id: 'tc-8',
    tool_name: 'predict_flight_impact',
    status: 'completed',
    start_time: '2025-10-21T12:00:09',
    end_time: '2025-10-21T12:00:10',
    input: {
      affected_areas: [
        ...spatialAnalysis.affected_stands,
        ...spatialAnalysis.affected_taxiways,
        ...spatialAnalysis.affected_runways,
      ],
    },
    output: `受影响航班${affectedFlightsList.length}架次, 累计延误${affectedFlightsList.reduce((sum, f) => sum + f.delay, 0)}分钟`,
  },
];

const totalDelay = affectedFlightsList.reduce((sum, flight) => sum + flight.delay, 0);
const delayDistribution = affectedFlightsList.reduce(
  (acc, flight) => {
    acc[flight.severity] += 1;
    return acc;
  },
  { severe: 0, moderate: 0, minor: 0 }
);

const leakSizeText = leakSizeLabel ? `，泄漏面积${leakSizeLabel}` : '';
const continuousText = defaultSample.key_factors.continuous ? '持续泄漏' : '少量渗漏';

// 模拟消息历史
export const mockMessages: Message[] = [
  {
    id: 'msg-1',
    role: 'user',
    content: defaultSample.input_text,
    timestamp: '2025-10-21T12:00:00',
  },
  {
    id: 'msg-2',
    role: 'assistant',
    content: `收到，正在分析 ${defaultFlight} 航班在 ${positionLabel} 的${fluidLabel}泄漏事件...`,
    timestamp: '2025-10-21T12:00:01',
    tool_calls: mockToolCalls.slice(0, 4),
    thinking: `识别到航班号 ${defaultFlight}，位置 ${positionLabel}，油液类型为${fluidLabel}，发动机${engineLabel}，${continuousText}${leakSizeText}。需要立即评估风险并联动相关部门。`,
  },
  {
    id: 'msg-3',
    role: 'assistant',
    content: `## 风险评估结果\n\n**风险等级: ${defaultSample.expected_risk_level}** - 评分: ${defaultSample.expected_score}/100\n\n### 关键因素:\n- ${fluidLabel}泄漏\n- 发动机${engineLabel}\n- ${continuousText}${leakSizeText ? `\n- 泄漏面积${leakSizeLabel}` : ''}\n\n### 即时措施:\n1. 已通知消防部门 ✓\n2. 已通知运行中心 ✓\n3. 建议设置警戒区域并准备吸油材料\n\n正在计算影响范围和航班影响...`,
    timestamp: '2025-10-21T12:00:08',
    tool_calls: mockToolCalls.slice(4),
  },
  {
    id: 'msg-4',
    role: 'assistant',
    content: `## 影响分析完成\n\n### 空间影响范围:\n- 受影响机位: ${spatialAnalysis.affected_stands.join('、') || '暂无'}\n- 受影响滑行道: ${spatialAnalysis.affected_taxiways.join('、') || '暂无'}\n- 可能影响跑道: ${spatialAnalysis.affected_runways.join('、') || '暂无'}\n\n### 航班影响预测:\n- 受影响航班: **${affectedFlightsList.length}架次**\n- 累计延误: **${totalDelay}分钟**\n- 平均延误: ${affectedFlightsList.length ? Math.round(totalDelay / affectedFlightsList.length) : 0}分钟/架次\n\n### 延误分布:\n- 严重延误 (≥60分钟): ${delayDistribution.severe}架次\n- 中等延误 (20-59分钟): ${delayDistribution.moderate}架次\n- 轻微延误 (<20分钟): ${delayDistribution.minor}架次\n\n### 处置建议:\n1. **高优先级** - 疏散相邻机位，设置警戒线\n2. **尽快执行** - 清污作业与滑行道绕行评估\n3. **持续监控** - 油污扩散与烟雾情况\n\n是否需要生成完整处置报告？`,
    timestamp: '2025-10-21T12:00:12',
  },
];

// 模拟完整会话状态
export const mockSessionState: SessionState = {
  session_id: 'session-demo-20251021-120000',
  incident: {
    flight_no: defaultFlight,
    position: defaultSample.key_factors.position || '',
    fluid_type: defaultSample.key_factors.fluid_type || 'OIL',
    engine_status: defaultSample.key_factors.engine_status || 'STOPPED',
    continuous: Boolean(defaultSample.key_factors.continuous),
    leak_size: defaultSample.key_factors.leak_size,
    incident_time: '2025-10-21T12:00:00',
    scenario_type: 'oil_spill',
  },
  risk_assessment: riskAssessment,
  spatial_analysis: spatialAnalysis,
  flight_impact: {
    affected_count: affectedFlightsList.length,
    total_delay_minutes: totalDelay,
    average_delay: affectedFlightsList.length ? Math.round(totalDelay / affectedFlightsList.length) : 0,
    flights: affectedFlightsList,
    delay_distribution: delayDistribution,
  },
  fsm_state: 'P4_AREA_ISOLATION',
  actions_taken: [
    { action: 'get_aircraft_info', status: 'completed', time: '12:00:02' },
    { action: 'assess_risk', status: 'completed', time: '12:00:06' },
    { action: 'notify_fire_dept', status: 'completed', department: '消防', time: '12:00:07' },
    { action: 'notify_ops_center', status: 'completed', department: '运行中心', time: '12:00:08' },
    { action: 'analyze_impact', status: 'completed', time: '12:00:10' },
  ],
  messages: mockMessages,
  checklist: mockChecklist,
  created_at: '2025-10-21T12:00:00',
  updated_at: '2025-10-21T12:00:12',
};

// 模拟 API 响应的函数
export const mockApi = {
  // 延迟函数
  delay: (ms: number) => new Promise((resolve) => setTimeout(resolve, ms)),

  // 模拟开始会话
  startSession: async () => {
    await mockApi.delay(500);
    return {
      success: true,
      data: {
        session_id: mockSessionState.session_id,
        state: {
          ...mockSessionState,
          messages: [],
          fsm_state: 'INIT' as const,
          risk_assessment: undefined,
          spatial_analysis: undefined,
          flight_impact: undefined,
          actions_taken: [],
        },
      },
    };
  },

  // 模拟发送消息 - 逐步返回状态
  chat: async (step: number) => {
    await mockApi.delay(1000);

    const states = [
      // Step 1: 初始识别
      {
        messages: mockMessages.slice(0, 2),
        fsm_state: 'P1_RISK_ASSESS' as const,
        incident: mockSessionState.incident,
        tool_calls: mockToolCalls.slice(0, 4),
      },
      // Step 2: 风险评估完成 + 通知
      {
        messages: mockMessages.slice(0, 3),
        fsm_state: 'P2_IMMEDIATE_CONTROL' as const,
        risk_assessment: mockSessionState.risk_assessment,
        actions_taken: mockSessionState.actions_taken.slice(0, 4),
        tool_calls: mockToolCalls.slice(4, 6),
      },
      // Step 3: 影响分析完成
      {
        messages: mockMessages,
        fsm_state: 'P4_AREA_ISOLATION' as const,
        spatial_analysis: mockSessionState.spatial_analysis,
        flight_impact: mockSessionState.flight_impact,
        checklist: mockChecklist,
        actions_taken: mockSessionState.actions_taken,
        tool_calls: mockToolCalls.slice(6),
      },
    ];

    const currentState = states[Math.min(step, states.length - 1)];

    return {
      success: true,
      data: {
        session_id: mockSessionState.session_id,
        response: mockMessages[step + 1]?.content || '处理完成',
        state: currentState,
        tool_calls: currentState.tool_calls,
        thinking: mockMessages[step + 1]?.thinking,
      },
    };
  },

  // 获取完整会话状态
  getSession: async () => {
    await mockApi.delay(200);
    return {
      success: true,
      data: mockSessionState,
    };
  },
};

export default mockApi;
