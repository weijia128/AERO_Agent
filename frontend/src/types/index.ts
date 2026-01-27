// AERO Agent 前端类型定义

// 事件类型
export type IncidentType = 'oil_spill' | 'bird_strike' | 'tire_burst' | 'runway_incursion';

// 风险等级
export type RiskLevel = 'R1' | 'R2' | 'R3' | 'R4';

// FSM 状态
export type FSMState = string;

// FSM 状态定义
export interface FSMStateDefinition {
  id: string;
  name: string;
  description?: string;
  order?: number;
}

// 油液类型
export type FluidType = 'FUEL' | 'HYDRAULIC' | 'OIL' | 'UNKNOWN';

// 发动机状态
export type EngineStatus = 'RUNNING' | 'STOPPED' | 'APU';

// 工具调用状态
export type ToolStatus = 'pending' | 'running' | 'completed' | 'failed';

// 事件信息
export interface Incident {
  flight_no: string;
  position: string;
  fluid_type?: FluidType;
  engine_status?: EngineStatus;
  continuous?: boolean;
  leak_size?: string;
  incident_time?: string;
  scenario_type?: IncidentType;
}

// 风险评估结果
export interface RiskAssessment {
  level: RiskLevel;
  score: number;
  factors: string[];
  rules_triggered: string[];
  cross_validation?: CrossValidation;
  validation_report?: Record<string, unknown>;
}

// 交叉验证结果
export interface CrossValidation {
  rule_result: RiskLevel;
  rule_score: number;
  llm_result: RiskLevel;
  llm_confidence: number;
  consistent: boolean;
  resolution?: string;
  needs_review?: boolean;
}

// 空间分析结果
export interface SpatialAnalysis {
  affected_stands: string[];
  affected_taxiways: string[];
  affected_runways: string[];
  impact_radius: number;
  spread_animation?: SpreadStep[];
}

// 扩散动画步骤
export interface SpreadStep {
  time: number;
  nodes: string[];
  color: string;
}

// 航班影响
export interface FlightImpact {
  affected_count: number;
  total_delay_minutes: number;
  average_delay: number;
  flights: AffectedFlight[];
  delay_distribution: {
    severe: number;
    moderate: number;
    minor: number;
  };
}

// 受影响航班
export interface AffectedFlight {
  callsign: string;
  aircraft_type?: string;
  stand?: string;
  runway?: string;
  scheduled_time?: string;
  delay: number;
  severity: 'severe' | 'moderate' | 'minor';
}

// 工具调用记录
export interface ToolCall {
  id: string;
  tool_name: string;
  status: ToolStatus;
  start_time: string;
  end_time?: string;
  input?: Record<string, unknown>;
  output?: string;
}

// 推理步骤
export interface ReasoningStep {
  step: number;
  thought: string;
  action?: string;
  action_input?: Record<string, unknown>;
  observation?: string;
}

// 处置动作
export interface Action {
  action: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  department?: string;
  time?: string;
  description?: string;
}

// 消息类型
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_calls?: ToolCall[];
  thinking?: string;
}

// 会话状态
export interface SessionState {
  session_id: string;
  incident: Incident;
  risk_assessment?: RiskAssessment;
  spatial_analysis?: SpatialAnalysis;
  flight_impact?: FlightImpact;
  fsm_state: FSMState;
  fsm_states?: FSMStateDefinition[];
  actions_taken: Action[];
  messages: Message[];
  checklist: ChecklistItem[];
  created_at: string;
  updated_at: string;
}

// 检查清单项
export interface ChecklistItem {
  id: string;
  phase: 'P1' | 'P2' | 'P3';
  item: string;
  completed: boolean;
  department?: string;
  deadline?: string;
}

// 天气信息
export interface Weather {
  timestamp: string;
  location_id: string;
  temperature: number;
  dew_point: number;
  relative_humidity: number;
  visibility: number;
  wind_direction: number;
  wind_speed: number;
  qnh: number;
}

// 拓扑节点
export interface TopologyNode {
  id: string;
  name: string;
  type: 'stand' | 'taxiway' | 'runway' | 'fire_station';
  coordinates: [number, number];
  adjacent?: string[];
  terminal?: string;
  zone?: string;
}

// API 响应
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// 会话启动请求
export interface StartSessionRequest {
  scenario_type?: IncidentType;
  initial_message?: string;
}

// 聊天请求
export interface ChatRequest {
  session_id: string;
  message: string;
}

// 聊天响应
export interface ChatResponse {
  session_id: string;
  response: string;
  state: Partial<SessionState>;
  tool_calls?: ToolCall[];
  thinking?: string;
}

// 预设场景
export interface PresetScenario {
  id: string;
  name: string;
  description: string;
  initial_message: string;
  expected_risk_level: RiskLevel;
  scenario_type: IncidentType;
}

// UI 状态
export interface UIState {
  bigScreenMode: boolean;
  demoMode: boolean;
  showReasoningTrace: boolean;
  selectedScenario?: string;
  loading: boolean;
  error?: string;
}

// 导出配置
export interface ExportConfig {
  format: 'pdf' | 'markdown';
  includeCharts: boolean;
  includeTimeline: boolean;
  includeRawData: boolean;
}
