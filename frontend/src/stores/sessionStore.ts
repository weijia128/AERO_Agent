import { create } from 'zustand';
import type {
  SessionState,
  Message,
  Incident,
  RiskAssessment,
  SpatialAnalysis,
  FlightImpact,
  FSMState,
  FSMStateDefinition,
  Action,
  ToolCall,
  ChecklistItem,
  ReasoningStep,
} from '../types';

interface SessionStore {
  // 会话状态
  sessionId: string | null;
  incident: Incident | null;
  riskAssessment: RiskAssessment | null;
  spatialAnalysis: SpatialAnalysis | null;
  flightImpact: FlightImpact | null;
  fsmState: FSMState;
  fsmStates: FSMStateDefinition[];
  actions: Action[];
  messages: Message[];
  checklist: ChecklistItem[];
  currentToolCalls: ToolCall[];
  reasoningSteps: ReasoningStep[];

  // 加载状态
  isLoading: boolean;
  isThinking: boolean;
  currentThinking: string;

  // Actions
  setSessionId: (id: string) => void;
  setIncident: (incident: Incident) => void;
  updateIncident: (updates: Partial<Incident>) => void;
  setRiskAssessment: (assessment: RiskAssessment) => void;
  setSpatialAnalysis: (analysis: SpatialAnalysis) => void;
  setFlightImpact: (impact: FlightImpact) => void;
  setFSMState: (state: FSMState) => void;
  setFSMStates: (states: FSMStateDefinition[]) => void;
  addAction: (action: Action) => void;
  updateAction: (actionName: string, updates: Partial<Action>) => void;
  addMessage: (message: Message) => void;
  setChecklist: (checklist: ChecklistItem[]) => void;
  updateChecklist: (itemId: string, completed: boolean) => void;
  setToolCalls: (toolCalls: ToolCall[]) => void;
  updateToolCall: (id: string, updates: Partial<ToolCall>) => void;
  setReasoningSteps: (steps: ReasoningStep[]) => void;
  addReasoningStep: (step: ReasoningStep) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean, content?: string) => void;
  resetSession: () => void;
  loadSession: (state: Partial<SessionState>) => void;
}

const initialState = {
  sessionId: null,
  incident: null,
  riskAssessment: null,
  spatialAnalysis: null,
  flightImpact: null,
  fsmState: 'INIT' as FSMState,
  fsmStates: [],
  actions: [],
  messages: [],
  checklist: [],
  currentToolCalls: [],
  reasoningSteps: [],
  isLoading: false,
  isThinking: false,
  currentThinking: '',
};

export const useSessionStore = create<SessionStore>((set) => ({
  ...initialState,

  setSessionId: (id) => set({ sessionId: id }),

  setIncident: (incident) => set({ incident }),

  updateIncident: (updates) =>
    set((state) => ({
      incident: state.incident ? { ...state.incident, ...updates } : null,
    })),

  setRiskAssessment: (assessment) => set({ riskAssessment: assessment }),

  setSpatialAnalysis: (analysis) => set({ spatialAnalysis: analysis }),

  setFlightImpact: (impact) => set({ flightImpact: impact }),

  setFSMState: (fsmState) => set({ fsmState }),

  setFSMStates: (fsmStates) => set({ fsmStates }),

  addAction: (action) =>
    set((state) => ({
      actions: [...state.actions, action],
    })),

  updateAction: (actionName, updates) =>
    set((state) => ({
      actions: state.actions.map((a) =>
        a.action === actionName ? { ...a, ...updates } : a
      ),
    })),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg)),
    })),

  setChecklist: (checklist) => set({ checklist }),

  updateChecklist: (itemId, completed) =>
    set((state) => ({
      checklist: state.checklist.map((item) =>
        item.id === itemId ? { ...item, completed } : item
      ),
    })),

  setToolCalls: (toolCalls) => set({ currentToolCalls: toolCalls }),

  updateToolCall: (id, updates) =>
    set((state) => ({
      currentToolCalls: state.currentToolCalls.map((tc) =>
        tc.id === id ? { ...tc, ...updates } : tc
      ),
    })),

  setReasoningSteps: (reasoningSteps) => set({ reasoningSteps }),

  addReasoningStep: (step) =>
    set((state) => ({
      reasoningSteps: [...state.reasoningSteps, step],
    })),

  setLoading: (isLoading) => set({ isLoading }),

  setThinking: (isThinking, content = '') =>
    set({ isThinking, currentThinking: content }),

  resetSession: () => set(initialState),

  loadSession: (sessionState) =>
    set((state) => ({
      sessionId: sessionState.session_id ?? state.sessionId,
      incident: sessionState.incident ?? state.incident,
      riskAssessment: sessionState.risk_assessment ?? state.riskAssessment,
      spatialAnalysis: sessionState.spatial_analysis ?? state.spatialAnalysis,
      flightImpact: sessionState.flight_impact ?? state.flightImpact,
      fsmState: sessionState.fsm_state ?? state.fsmState,
      fsmStates: sessionState.fsm_states ?? state.fsmStates,
      actions: sessionState.actions_taken ?? state.actions,
      messages: sessionState.messages ?? state.messages,
      checklist: sessionState.checklist ?? state.checklist,
    })),
}));
