import axios, { type AxiosInstance, type AxiosError } from 'axios';
import type { FSMStateDefinition } from '../types';

// 工具调用信息
export interface ToolCallInfo {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

// 推理步骤信息
export interface ReasoningStepInfo {
  step: number;
  thought: string;
  action?: string;
  action_input?: Record<string, unknown>;
  observation?: string;
}

// 后端 API 响应类型（匹配 Python EventResponse）
export interface EventResponse {
  session_id: string;
  status: 'processing' | 'completed' | 'error';
  message: string;
  report?: Record<string, unknown>;
  fsm_state: string;
  checklist: Record<string, boolean>;
  risk_level?: string;
  scenario_type?: string;
  incident?: Record<string, unknown>;
  fsm_states?: FSMStateDefinition[];
  next_question?: string;
  // 工具调用和推理过程
  tool_calls?: ToolCallInfo[];
  reasoning_steps?: ReasoningStepInfo[];
  current_thought?: string;
  spatial_analysis?: Record<string, unknown>;
  flight_impact_prediction?: Record<string, unknown>;
}

// 会话状态响应
export interface SessionStatusResponse {
  session_id: string;
  fsm_state: string;
  checklist: Record<string, boolean>;
  risk_assessment?: {
    level: string;
    score: number;
    factors?: string[];
    rules_triggered?: string[];
  };
  spatial_analysis?: {
    isolated_nodes?: string[];
    affected_stands?: string[];
    affected_taxiways?: string[];
    affected_runways?: string[];
  };
  flight_impact_prediction?: {
    statistics?: {
      total_affected_flights: number;
      average_delay_minutes: number;
      severity_distribution?: {
        high: number;
        medium: number;
        low: number;
      };
    };
    affected_flights?: Array<{
      callsign: string;
      estimated_delay_minutes: number;
      delay_reason: string;
    }>;
  };
  is_complete: boolean;
  iteration_count: number;
}

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 60000, // 增加超时时间到60秒，因为 LLM 调用可能较慢
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证 token
    const apiKey = localStorage.getItem('api_key');
    if (apiKey) {
      config.headers['X-API-Key'] = apiKey;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // 统一错误处理
    const message = error.response?.data
      ? (error.response.data as { detail?: string }).detail || '请求失败'
      : error.message;
    console.error('API Error:', message);
    return Promise.reject(new Error(message));
  }
);

// API 服务
export const api = {
  /**
   * 开始新会话
   */
  startSession: async (params: {
    message: string;
    scenario_type?: string;
    session_id?: string;
  }): Promise<EventResponse> => {
    const response = await apiClient.post('/event/start', params);
    return response.data;
  },

  /**
   * 发送消息（继续对话）
   */
  chat: async (params: {
    session_id: string;
    message: string;
  }): Promise<EventResponse> => {
    const response = await apiClient.post('/event/chat', params);
    return response.data;
  },

  /**
   * 获取会话状态
   */
  getSession: async (sessionId: string): Promise<SessionStatusResponse> => {
    const response = await apiClient.get(`/event/${sessionId}`);
    return response.data;
  },

  /**
   * 获取会话报告（JSON）
   */
  getReport: async (sessionId: string): Promise<Record<string, unknown>> => {
    const response = await apiClient.get(`/event/${sessionId}/report`);
    return response.data;
  },

  /**
   * 获取会话报告（Markdown）
   */
  getReportMarkdown: async (sessionId: string): Promise<Blob> => {
    const response = await apiClient.get(`/event/${sessionId}/report/markdown`, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * 关闭会话
   */
  closeSession: async (sessionId: string): Promise<{ status: string; session_id: string }> => {
    const response = await apiClient.delete(`/event/${sessionId}`);
    return response.data;
  },

  /**
   * 流式开始新会话 (SSE)
   */
  startSessionStream: (
    params: {
      message: string;
      scenario_type?: string;
      session_id?: string;
    },
    callbacks: StreamCallbacks
  ): AbortController => {
    return createSSEConnection('/api/event/start/stream', params, callbacks);
  },

  /**
   * 流式发送消息 (SSE)
   */
  chatStream: (
    params: {
      session_id: string;
      message: string;
    },
    callbacks: StreamCallbacks
  ): AbortController => {
    return createSSEConnection('/api/event/chat/stream', params, callbacks);
  },

  parseEvent: async (params: { message: string; scenario_type?: string }): Promise<ParseEventResponse> => {
    const response = await apiClient.post('/event/parse', params);
    return response.data as ParseEventResponse;
  },
};

// SSE 流式事件类型
export interface StreamEvent {
  node?: string;
  timestamp?: string;
  session_id?: string;
  fsm_state?: string;
  checklist?: Record<string, boolean>;
  current_thought?: string;
  current_action?: string;
  current_action_input?: Record<string, unknown>;
  current_observation?: string;
  reasoning_steps?: ReasoningStepInfo[];
  scenario_type?: string;
  incident?: Record<string, unknown>;
  fsm_states?: FSMStateDefinition[];
  tool_calls?: ToolCallInfo[];
  risk_assessment?: {
    level: string;
    score?: number;
    factors?: string[];
    rules_triggered?: string[];
    validation_report?: Record<string, unknown>;
  };
  spatial_analysis?: Record<string, unknown>;
  flight_impact_prediction?: Record<string, unknown>;
  is_complete?: boolean;
  final_answer?: string;
  next_question?: string;
  status?: string;
  error?: string;
  risk_level?: string;
}

// 流式回调接口
export interface StreamCallbacks {
  onNodeUpdate?: (event: StreamEvent) => void;
  onComplete?: (event: StreamEvent) => void;
  onError?: (error: Error | StreamEvent) => void;
}

export interface ParseEventResponse {
  scenario_type?: string;
  incident?: Record<string, unknown>;
  checklist?: Record<string, boolean>;
  enrichment_observation?: string;
}

// 创建 SSE 连接
function createSSEConnection(
  url: string,
  params: Record<string, unknown>,
  callbacks: StreamCallbacks
): AbortController {
  const abortController = new AbortController();

  // 使用 fetch 发送 POST 请求并处理 SSE 响应
  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': localStorage.getItem('api_key') || '',
    },
    body: JSON.stringify(params),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 解析 SSE 事件
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 保留不完整的行

        let currentEvent = '';
        let currentData = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            currentData = line.slice(5).trim();
          } else if (line === '' && currentData) {
            // 空行表示事件结束
            try {
              const eventData = JSON.parse(currentData) as StreamEvent;

              if (currentEvent === 'node_update') {
                callbacks.onNodeUpdate?.(eventData);
              } else if (currentEvent === 'complete') {
                callbacks.onComplete?.(eventData);
              } else if (currentEvent === 'error') {
                callbacks.onError?.(eventData);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e, currentData);
            }

            currentEvent = '';
            currentData = '';
          }
        }
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        callbacks.onError?.(error);
      }
    });

  return abortController;
}

export default api;
