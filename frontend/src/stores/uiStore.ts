import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIStore {
  // 模式设置
  bigScreenMode: boolean;
  demoMode: boolean;
  showReasoningTrace: boolean;

  // 当前选择
  selectedScenarioId: string | null;
  activeTab: string;

  // 错误状态
  error: string | null;

  // Actions
  toggleBigScreenMode: () => void;
  setBigScreenMode: (enabled: boolean) => void;
  toggleDemoMode: () => void;
  setDemoMode: (enabled: boolean) => void;
  toggleReasoningTrace: () => void;
  setSelectedScenario: (id: string | null) => void;
  setActiveTab: (tab: string) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      // 初始状态
      bigScreenMode: false,
      demoMode: false, // 默认使用真实后端
      showReasoningTrace: true,
      selectedScenarioId: null,
      activeTab: 'chat',
      error: null,

      // Actions
      toggleBigScreenMode: () =>
        set((state) => ({ bigScreenMode: !state.bigScreenMode })),

      setBigScreenMode: (enabled) => set({ bigScreenMode: enabled }),

      toggleDemoMode: () => set((state) => ({ demoMode: !state.demoMode })),

      setDemoMode: (enabled) => set({ demoMode: enabled }),

      toggleReasoningTrace: () =>
        set((state) => ({ showReasoningTrace: !state.showReasoningTrace })),

      setSelectedScenario: (id) => set({ selectedScenarioId: id }),

      setActiveTab: (tab) => set({ activeTab: tab }),

      setError: (error) => set({ error }),

      clearError: () => set({ error: null }),
    }),
    {
      name: 'aero-agent-ui',
      version: 2,
      migrate: (state) => {
        const next = state as UIStore;
        return {
          ...next,
          demoMode: false,
        };
      },
      partialize: (state) => ({
        bigScreenMode: state.bigScreenMode,
        demoMode: state.demoMode,
        showReasoningTrace: state.showReasoningTrace,
      }),
    }
  )
);
