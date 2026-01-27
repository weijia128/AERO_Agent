import type {
  SessionState,
  Message,
  ToolCall,
  ChecklistItem,
  PresetScenario,
  Weather,
  TopologyNode,
  AffectedFlight,
} from '../types';

// 预设演示场景
export const presetScenarios: PresetScenario[] = [
  {
    id: 'oil-spill-high-risk',
    name: '燃油泄漏 - 高风险',
    description: 'CES2876 在 501 机位燃油泄漏，发动机运转中，持续滴漏',
    initial_message: 'CES2876在501机位漏油了，燃油，发动机还在转，持续滴漏',
    expected_risk_level: 'R4',
    scenario_type: 'oil_spill',
  },
  {
    id: 'oil-spill-medium-risk',
    name: '液压油泄漏 - 中风险',
    description: 'MU5208 在 T2-15 机位液压油泄漏，发动机已停',
    initial_message: 'MU5208航班在T2-15机位有液压油泄漏，发动机已经关了',
    expected_risk_level: 'R2',
    scenario_type: 'oil_spill',
  },
  {
    id: 'oil-spill-low-risk',
    name: '润滑油泄漏 - 低风险',
    description: 'CA1234 在 502 机位少量润滑油泄漏',
    initial_message: 'CA1234在502机位发现少量润滑油，已经停止泄漏了',
    expected_risk_level: 'R1',
    scenario_type: 'oil_spill',
  },
];

// 模拟天气数据
export const mockWeather: Weather = {
  timestamp: '2026-01-06T10:00:00',
  location_id: 'ZBAA',
  temperature: 5,
  dew_point: -2,
  relative_humidity: 45,
  visibility: 9999,
  wind_direction: 320,
  wind_speed: 12,
  qnh: 1013,
};

// 模拟拓扑节点（简化版）
export const mockTopologyNodes: TopologyNode[] = [
  { id: '501', name: '501机位', type: 'stand', coordinates: [116.584, 40.08], adjacent: ['502', '503', 'taxiway_A'], terminal: 'T2', zone: 'A' },
  { id: '502', name: '502机位', type: 'stand', coordinates: [116.585, 40.08], adjacent: ['501', '503', 'taxiway_A'], terminal: 'T2', zone: 'A' },
  { id: '503', name: '503机位', type: 'stand', coordinates: [116.586, 40.08], adjacent: ['501', '502', 'taxiway_A'], terminal: 'T2', zone: 'A' },
  { id: '504', name: '504机位', type: 'stand', coordinates: [116.587, 40.08], adjacent: ['taxiway_A'], terminal: 'T2', zone: 'A' },
  { id: '505', name: '505机位', type: 'stand', coordinates: [116.588, 40.08], adjacent: ['taxiway_A'], terminal: 'T2', zone: 'A' },
  { id: 'taxiway_A', name: 'A滑行道', type: 'taxiway', coordinates: [116.585, 40.079], adjacent: ['501', '502', '503', '504', '505', 'runway_01L'] },
  { id: 'runway_01L', name: '01L跑道', type: 'runway', coordinates: [116.58, 40.07], adjacent: ['taxiway_A'] },
  { id: 'fire_station_1', name: '消防站1', type: 'fire_station', coordinates: [116.582, 40.075] },
];

// 模拟受影响航班
export const mockAffectedFlights: AffectedFlight[] = [
  { callsign: 'MU5101', aircraft_type: 'A320', stand: '502', runway: '01L', scheduled_time: '2026-01-06 10:15:00', delay: 60, severity: 'severe' },
  { callsign: 'CA1234', aircraft_type: 'B737', stand: '503', runway: '01L', scheduled_time: '2026-01-06 10:20:00', delay: 60, severity: 'severe' },
  { callsign: 'CZ3456', aircraft_type: 'A321', stand: '504', runway: '01L', scheduled_time: '2026-01-06 10:25:00', delay: 60, severity: 'severe' },
  { callsign: 'HU7890', aircraft_type: 'B787', stand: '505', runway: '01L', scheduled_time: '2026-01-06 10:30:00', delay: 60, severity: 'severe' },
  { callsign: '3U8765', aircraft_type: 'A319', stand: '506', runway: '01L', scheduled_time: '2026-01-06 10:35:00', delay: 60, severity: 'severe' },
  { callsign: 'FM9876', aircraft_type: 'B738', stand: '507', runway: '01L', scheduled_time: '2026-01-06 10:40:00', delay: 60, severity: 'severe' },
  { callsign: 'ZH1234', aircraft_type: 'A320', stand: '508', runway: '01L', scheduled_time: '2026-01-06 10:45:00', delay: 60, severity: 'severe' },
];

// 模拟检查清单
export const mockChecklist: ChecklistItem[] = [
  { id: 'p1-1', phase: 'P1', item: '确认油液类型', completed: true, department: '机务' },
  { id: 'p1-2', phase: 'P1', item: '确认发动机状态', completed: true, department: '机务' },
  { id: 'p1-3', phase: 'P1', item: '确认泄漏状态', completed: true, department: '机务' },
  { id: 'p1-4', phase: 'P1', item: '风险评估', completed: true, department: '系统' },
  { id: 'p2-1', phase: 'P2', item: '通知消防部门', completed: true, department: '消防', deadline: '立即' },
  { id: 'p2-2', phase: 'P2', item: '通知塔台', completed: true, department: '塔台', deadline: '立即' },
  { id: 'p2-3', phase: 'P2', item: '疏散相邻机位', completed: false, department: '运行', deadline: '5分钟' },
  { id: 'p2-4', phase: 'P2', item: '设置警戒区域', completed: false, department: '安保', deadline: '10分钟' },
  { id: 'p3-1', phase: 'P3', item: '启动清理作业', completed: false, department: '地服', deadline: '15分钟' },
  { id: 'p3-2', phase: 'P3', item: '协调延误航班', completed: false, department: '运行', deadline: '即时' },
];

// 模拟工具调用
export const mockToolCalls: ToolCall[] = [
  {
    id: 'tc-1',
    tool_name: 'get_aircraft_info',
    status: 'completed',
    start_time: '2026-01-06T10:00:01',
    end_time: '2026-01-06T10:00:02',
    input: { flight_no: 'CES2876' },
    output: 'A320, 计划08:35起飞, 507机位',
  },
  {
    id: 'tc-2',
    tool_name: 'get_topology_info',
    status: 'completed',
    start_time: '2026-01-06T10:00:02',
    end_time: '2026-01-06T10:00:03',
    input: { position: '501' },
    output: '501机位, 相邻: 502, 503, 滑行道A',
  },
  {
    id: 'tc-3',
    tool_name: 'get_weather',
    status: 'completed',
    start_time: '2026-01-06T10:00:03',
    end_time: '2026-01-06T10:00:04',
    input: { location: 'ZBAA' },
    output: '5°C, 风向320°, 风速12kt, 能见度9999m',
  },
  {
    id: 'tc-4',
    tool_name: 'assess_oil_spill_risk',
    status: 'completed',
    start_time: '2026-01-06T10:00:05',
    end_time: '2026-01-06T10:00:06',
    input: { fluid_type: 'FUEL', engine_status: 'RUNNING', continuous: true },
    output: 'R4 (90分) - 触发规则: FUEL + ENGINE_RUNNING + CONTINUOUS',
  },
  {
    id: 'tc-5',
    tool_name: 'analyze_impact_zone',
    status: 'completed',
    start_time: '2026-01-06T10:00:06',
    end_time: '2026-01-06T10:00:07',
    input: { position: '501', risk_level: 'R4' },
    output: '影响范围: 502, 503, 滑行道A, 可能影响01L跑道',
  },
  {
    id: 'tc-6',
    tool_name: 'predict_flight_impact',
    status: 'completed',
    start_time: '2026-01-06T10:00:07',
    end_time: '2026-01-06T10:00:08',
    input: { affected_areas: ['501', '502', '503', 'taxiway_A', 'runway_01L'] },
    output: '受影响航班7架次, 累计延误420分钟',
  },
  {
    id: 'tc-7',
    tool_name: 'notify_department',
    status: 'completed',
    start_time: '2026-01-06T10:00:09',
    end_time: '2026-01-06T10:00:10',
    input: { department: 'fire', priority: 'immediate' },
    output: '消防部门已通知',
  },
  {
    id: 'tc-8',
    tool_name: 'notify_department',
    status: 'completed',
    start_time: '2026-01-06T10:00:10',
    end_time: '2026-01-06T10:00:11',
    input: { department: 'tower', priority: 'immediate' },
    output: '塔台已通知',
  },
];

// 模拟消息历史
export const mockMessages: Message[] = [
  {
    id: 'msg-1',
    role: 'user',
    content: 'CES2876在501机位漏油了，燃油，发动机还在转，持续滴漏',
    timestamp: '2026-01-06T10:00:00',
  },
  {
    id: 'msg-2',
    role: 'assistant',
    content: '收到，正在分析 CES2876 航班在 501 机位的燃油泄漏事件...',
    timestamp: '2026-01-06T10:00:01',
    tool_calls: mockToolCalls.slice(0, 4),
    thinking: '识别到航班号 CES2876，位置 501 机位，油液类型为燃油，发动机运转中，持续滴漏。这是一个高风险场景，需要立即评估并通知相关部门。',
  },
  {
    id: 'msg-3',
    role: 'assistant',
    content: `## 风险评估结果

**风险等级: R4 (高风险)** - 评分: 90/100

### 触发规则:
- Rule #1: FUEL (燃油) - 30分
- Rule #5: ENGINE_RUNNING (发动机运转) - 30分
- Rule #3: CONTINUOUS (持续滴漏) - 30分

### 交叉验证:
- 规则引擎: R4 (90分)
- LLM验证: R4 (置信度 92%)
- **结果一致** ✓

### 即时措施:
1. 已通知消防部门 ✓
2. 已通知塔台 ✓
3. 建议立即疏散相邻机位 (502, 503)
4. 建议设置警戒区域

正在计算影响范围和航班影响...`,
    timestamp: '2026-01-06T10:00:08',
    tool_calls: mockToolCalls.slice(4),
  },
  {
    id: 'msg-4',
    role: 'assistant',
    content: `## 影响分析完成

### 空间影响范围:
- 受影响机位: 501, 502, 503, 504, 505 (5个)
- 受影响滑行道: A滑行道
- 可能影响跑道: 01L

### 航班影响预测:
- 分析时间窗口: 10:00 - 11:10 (70分钟)
- 受影响航班: **7架次**
- 累计延误: **420分钟**
- 平均延误: 60分钟/架次

### 延误分布:
- 严重延误 (≥60分钟): 7架次
- 中等延误 (20-59分钟): 0架次
- 轻微延误 (<20分钟): 0架次

### 处置建议:
1. **立即执行** - 疏散 502, 503 机位航班
2. **高优先级** - 协调 7 架次延误航班
3. **持续监控** - 油污扩散情况

是否需要生成完整处置报告？`,
    timestamp: '2026-01-06T10:00:12',
  },
];

// 模拟完整会话状态
export const mockSessionState: SessionState = {
  session_id: 'session-demo-20260106-100000',
  incident: {
    flight_no: 'CES2876',
    position: '501',
    fluid_type: 'FUEL',
    engine_status: 'RUNNING',
    continuous: true,
    incident_time: '2026-01-06T10:00:00',
    scenario_type: 'oil_spill',
  },
  risk_assessment: {
    level: 'R4',
    score: 90,
    factors: ['FUEL', 'ENGINE_RUNNING', 'CONTINUOUS'],
    rules_triggered: [
      'Rule #1: FUEL (燃油) - 30分',
      'Rule #5: ENGINE_RUNNING (发动机运转) - 30分',
      'Rule #3: CONTINUOUS (持续滴漏) - 30分',
    ],
    cross_validation: {
      rule_result: 'R4',
      rule_score: 90,
      llm_result: 'R4',
      llm_confidence: 0.92,
      consistent: true,
    },
  },
  spatial_analysis: {
    affected_stands: ['502', '503', '504', '505'],
    affected_taxiways: ['taxiway_A'],
    affected_runways: ['runway_01L'],
    impact_radius: 3,
    spread_animation: [
      { time: 0, nodes: ['501'], color: '#f85149' },
      { time: 1, nodes: ['502', '503'], color: '#d29922' },
      { time: 2, nodes: ['taxiway_A'], color: '#fadb14' },
      { time: 3, nodes: ['runway_01L'], color: '#f85149' },
    ],
  },
  flight_impact: {
    affected_count: 7,
    total_delay_minutes: 420,
    average_delay: 60,
    flights: mockAffectedFlights,
    delay_distribution: {
      severe: 7,
      moderate: 0,
      minor: 0,
    },
  },
  fsm_state: 'P3_IMPACT_ANALYSIS',
  actions_taken: [
    { action: 'get_aircraft_info', status: 'completed', time: '10:00:02' },
    { action: 'assess_risk', status: 'completed', time: '10:00:06' },
    { action: 'notify_fire_dept', status: 'completed', department: '消防', time: '10:00:10' },
    { action: 'notify_tower', status: 'completed', department: '塔台', time: '10:00:11' },
    { action: 'analyze_impact', status: 'completed', time: '10:00:12' },
  ],
  messages: mockMessages,
  checklist: mockChecklist,
  created_at: '2026-01-06T10:00:00',
  updated_at: '2026-01-06T10:00:12',
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
      // Step 2: 风险评估完成
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
        fsm_state: 'P3_IMPACT_ANALYSIS' as const,
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
