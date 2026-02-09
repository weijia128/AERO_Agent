import { useCallback, useState } from 'react';
import { useSessionStore } from '../stores/sessionStore';
import { useUIStore } from '../stores/uiStore';
import { api, mockApi, presetScenarios } from '../services';
import type { StreamEvent } from '../services/api';
import type { Message, FSMState, RiskLevel, ChecklistItem, ReasoningStep, Incident } from '../types';

const scenarioLabels: Record<string, string> = {
  oil_spill: '油污泄漏',
  bird_strike: '鸟击事件',
  fod: 'FOD 外来物',
  tire_burst: '轮胎爆破',
  runway_incursion: '跑道入侵',
};

let activeAbortController: AbortController | null = null;

export function useSession() {
  const {
    sessionId,
    messages,
    isLoading,
    isThinking,
    currentThinking,
    currentToolCalls,
    reasoningSteps,
    setSessionId,
    setIncident,
    updateIncident,
    setRiskAssessment,
    setSpatialAnalysis,
    setFlightImpact,
    setFSMState,
    setFSMStates,
    setChecklist,
    addAction,
    addMessage,
    updateMessage,
    setToolCalls,
    updateToolCall,
    setReasoningSteps,
    setLoading,
    setThinking,
    resetSession,
    loadSession,
  } = useSessionStore();

  const { demoMode, setError } = useUIStore();
  const [demoStep, setDemoStep] = useState(0);

  // 处理流式事件更新
  const handleStreamEvent = useCallback(
    (event: StreamEvent) => {
      // 更新会话 ID 并添加系统消息
      if (event.session_id) {
        const prevSessionId = useSessionStore.getState().sessionId;
        setSessionId(event.session_id);
        // 首次设置会话 ID 时添加系统消息
        if (!prevSessionId && event.session_id) {
          const sysMessage: Message = {
            id: `msg-sys-session-${Date.now()}`,
            role: 'system',
            content: `[信息] 会话 ID: ${event.session_id}`,
            timestamp: new Date().toISOString(),
          };
          addMessage(sysMessage);
        }
      }

      // 更新 FSM 状态并添加状态变更消息
      if (event.fsm_state) {
        const prevFsmState = useSessionStore.getState().fsmState;
        if (prevFsmState !== event.fsm_state) {
          setFSMState(event.fsm_state as FSMState);
          // 添加 FSM 状态变更系统消息
          const fsmMessage: Message = {
            id: `msg-sys-fsm-${Date.now()}`,
            role: 'system',
            content: `[状态] FSM: ${prevFsmState} → ${event.fsm_state}`,
            timestamp: new Date().toISOString(),
          };
          addMessage(fsmMessage);
        } else {
          setFSMState(event.fsm_state as FSMState);
        }
      }

      if (event.fsm_states && event.fsm_states.length > 0) {
        setFSMStates(event.fsm_states);
      }

      // 更新 checklist
      if (event.checklist) {
        const checklistItems: ChecklistItem[] = Object.entries(event.checklist).map(
          ([key, completed], index) => ({
            id: `check-${index}`,
            phase: 'P1' as const,
            item: key,
            completed: completed as boolean,
          })
        );
        setChecklist(checklistItems);
      }

      // 更新当前思考状态（不展示内部推理细节）
      if (event.current_thought) {
        setThinking(true, '正在分析...');
      }

      // 更新推理步骤 - 实时添加新步骤
      if (event.reasoning_steps && event.reasoning_steps.length > 0) {
        const incomingSteps: ReasoningStep[] = event.reasoning_steps.map((rs) => {
          const summary = rs.action
            ? `调用工具: ${rs.action}`
            : rs.observation
              ? '处理工具反馈'
              : '推理更新';
          return {
            step: rs.step,
            thought: summary,
            action: rs.action,
            action_input: rs.action_input,
            observation: rs.observation,
          };
        });

        const existingSteps = useSessionStore.getState().reasoningSteps;
        const mergedSteps = [...existingSteps];
        incomingSteps.forEach((nextStep) => {
          const index = mergedSteps.findIndex((step) => step.step === nextStep.step);
          if (index >= 0) {
            mergedSteps[index] = { ...mergedSteps[index], ...nextStep };
          } else {
            mergedSteps.push(nextStep);
          }
        });
        mergedSteps.sort((a, b) => a.step - b.step);
        setReasoningSteps(mergedSteps);
        if (!event.tool_calls || event.tool_calls.length === 0) {
          const now = event.timestamp || new Date().toISOString();
          const derivedToolCalls = mergedSteps
            .filter((step) => step.action)
            .map((step, index) => ({
              id: `rs-${step.step}-${index}`,
              tool_name: step.action as string,
              status: step.observation ? ('completed' as const) : ('running' as const),
              start_time: now,
              end_time: step.observation ? now : undefined,
              input: step.action_input,
              output: step.observation,
            }));
          if (derivedToolCalls.length > 0) {
            setToolCalls(derivedToolCalls);
          }
        }
      }

      if (event.incident) {
        setIncident(event.incident as Incident);
      }

      const scenarioType =
        (event.scenario_type as string | undefined) ||
        ((event.incident as Incident | undefined)?.scenario_type as string | undefined);
      if (scenarioType) {
        const existingIncident = useSessionStore.getState().incident;
        if (existingIncident || event.incident) {
          updateIncident({ scenario_type: scenarioType as Incident['scenario_type'] });
        } else {
          setIncident({ scenario_type: scenarioType } as Incident);
        }
        const scenarioLabel = scenarioLabels[scenarioType] || scenarioType || '待识别';
        const existingMessages = useSessionStore.getState().messages;
        const existingScenario = existingMessages.find(
          (msg) => msg.role === 'system' && msg.content.startsWith('[信息] 识别场景')
        );
        if (existingScenario) {
          updateMessage(existingScenario.id, {
            content: `[信息] 识别场景: ${scenarioLabel}`,
            timestamp: new Date().toISOString(),
          });
        } else {
          addMessage({
            id: `msg-sys-scenario-${Date.now()}`,
            role: 'system',
            content: `[信息] 识别场景: ${scenarioLabel}`,
            timestamp: new Date().toISOString(),
          });
        }
      }

      if (event.tool_calls && event.tool_calls.length > 0) {
        const now = event.timestamp || new Date().toISOString();
        setToolCalls(
          event.tool_calls.map((call) => ({
            id: call.id,
            tool_name: call.name,
            status: call.status,
            start_time: now,
            end_time: call.status === 'completed' ? now : undefined,
            input: call.input,
            output: call.output,
          }))
        );
      }

      if (event.current_action) {
        const now = event.timestamp || new Date().toISOString();
        const actionId = `live-${event.current_action}`;
        const existingCalls = useSessionStore.getState().currentToolCalls;
        const existingCall = existingCalls.find(
          (call) => call.id === actionId || call.tool_name === event.current_action
        );
        if (existingCall) {
          updateToolCall(existingCall.id, {
            status: event.current_observation ? 'completed' : 'running',
            end_time: event.current_observation ? now : existingCall.end_time,
            input: event.current_action_input || existingCall.input,
            output: event.current_observation || existingCall.output,
          });
        } else {
          setToolCalls([
            ...existingCalls,
            {
              id: actionId,
              tool_name: event.current_action,
              status: event.current_observation ? 'completed' : 'running',
              start_time: now,
              end_time: event.current_observation ? now : undefined,
              input: event.current_action_input,
              output: event.current_observation,
            },
          ]);
        }
        setThinking(true, `正在执行 ${event.current_action}...`);
      }

      // 更新风险评估 - 包含交叉验证数据
      if (event.risk_assessment) {
        const riskLevel = (event.risk_assessment.level || event.risk_level) as RiskLevel;
        const riskScore =
          (event.risk_assessment.score as number | undefined) ??
          (event.risk_assessment as Record<string, unknown>).risk_score ??
          0;
        const rawAssessment = event.risk_assessment as Record<string, unknown>;
        const explanations = (rawAssessment.explanations as string[]) || [];
        const factors = (rawAssessment.factors as string[]) || explanations;
        const rulesTriggered =
          (rawAssessment.rules_triggered as string[]) ||
          explanations ||
          (rawAssessment.rationale ? [String(rawAssessment.rationale)] : []);
        let crossValidation: {
          rule_result: RiskLevel;
          rule_score: number;
          llm_result: RiskLevel;
          llm_confidence: number;
          consistent: boolean;
          resolution?: string;
          needs_review?: boolean;
        } | undefined;
        if (rawAssessment.cross_validation) {
          crossValidation = rawAssessment.cross_validation as {
            rule_result: RiskLevel;
            rule_score: number;
            llm_result: RiskLevel;
            llm_confidence: number;
            consistent: boolean;
            resolution?: string;
            needs_review?: boolean;
          };
        } else if (rawAssessment.validation_report) {
          const report = rawAssessment.validation_report as Record<string, unknown>;
          const ruleEngine = (report.rule_engine as Record<string, unknown>) || {};
          const llmValidation = (report.llm_validation as Record<string, unknown>) || {};
          const consistency = (report.consistency as Record<string, unknown>) || {};
          const finalDecision = (report.final_decision as Record<string, unknown>) || {};
          crossValidation = {
            rule_result: String(ruleEngine.level || riskLevel) as RiskLevel,
            rule_score: Number(ruleEngine.score ?? riskScore ?? 0),
            llm_result: String(llmValidation.level || riskLevel) as RiskLevel,
            llm_confidence: Number(llmValidation.confidence ?? 0),
            consistent: Boolean(consistency.is_consistent),
            resolution: typeof finalDecision.resolution_strategy === 'string'
              ? finalDecision.resolution_strategy
              : undefined,
            needs_review: Boolean(report.needs_manual_review),
          };
        }
        setRiskAssessment({
          level: riskLevel,
          score: riskScore,
          factors,
          rules_triggered: rulesTriggered,
          cross_validation: crossValidation,
          validation_report: rawAssessment.validation_report as Record<string, unknown> | undefined,
        });
        // 更新或添加风险评估系统消息（避免刷屏）
        const riskContent = `[风险] 评估等级: ${riskLevel} (${riskScore}分)`;
        const existingMessages = useSessionStore.getState().messages;
        const existingRisk = existingMessages.find(
          (msg) => msg.role === 'system' && msg.content.startsWith('[风险]')
        );
        if (existingRisk) {
          updateMessage(existingRisk.id, {
            content: riskContent,
            timestamp: new Date().toISOString(),
          });
        } else {
          addMessage({
            id: `msg-sys-risk-${Date.now()}`,
            role: 'system',
            content: riskContent,
            timestamp: new Date().toISOString(),
          });
        }
      } else if (event.risk_level) {
        const riskLevel = event.risk_level as RiskLevel;
        const storedRisk = useSessionStore.getState().riskAssessment;
        if (!storedRisk || !storedRisk.level) {
          setRiskAssessment({
            level: riskLevel,
            score: 0,
            factors: [],
            rules_triggered: [],
          });
        } else if (storedRisk.level !== riskLevel) {
          setRiskAssessment({
            ...storedRisk,
            level: riskLevel,
          });
        }
        const riskContent = `[风险] 评估等级: ${riskLevel} (0分)`;
        const existingMessages = useSessionStore.getState().messages;
        const existingRiskMessage = existingMessages.find(
          (msg) => msg.role === 'system' && msg.content.startsWith('[风险]')
        );
        if (existingRiskMessage) {
          updateMessage(existingRiskMessage.id, {
            content: riskContent,
            timestamp: new Date().toISOString(),
          });
        } else {
          addMessage({
            id: `msg-sys-risk-${Date.now()}`,
            role: 'system',
            content: riskContent,
            timestamp: new Date().toISOString(),
          });
        }
      }

      // 更新空间分析
      if (event.spatial_analysis) {
        const sa = event.spatial_analysis as Record<string, unknown>;
        setSpatialAnalysis({
          affected_stands: (sa.affected_stands as string[]) || (sa.isolated_nodes as string[]) || [],
          affected_taxiways: (sa.affected_taxiways as string[]) || [],
          affected_runways: (sa.affected_runways as string[]) || [],
          impact_radius: (sa.impact_radius as number) || 0,
          spread_animation: (sa.spread_animation as any) || undefined,
        });
      }

      // 更新航班影响
      if (event.flight_impact_prediction) {
        const fip = event.flight_impact_prediction as Record<string, unknown>;
        const stats = fip.statistics as Record<string, unknown> | undefined;
        if (stats) {
          setFlightImpact({
            affected_count: (stats.total_affected_flights as number) || 0,
            total_delay_minutes:
              ((stats.average_delay_minutes as number) || 0) *
              ((stats.total_affected_flights as number) || 0),
            average_delay: (stats.average_delay_minutes as number) || 0,
            flights: ((fip.affected_flights as Array<Record<string, unknown>>) || []).map((f) => ({
              callsign: f.callsign as string,
              delay: f.estimated_delay_minutes as number,
              severity:
                (f.estimated_delay_minutes as number) >= 60
                  ? ('severe' as const)
                  : (f.estimated_delay_minutes as number) >= 20
                    ? ('moderate' as const)
                    : ('minor' as const),
            })),
            delay_distribution: {
              severe: (stats.severity_distribution as Record<string, number>)?.high || 0,
              moderate: (stats.severity_distribution as Record<string, number>)?.medium || 0,
              minor: (stats.severity_distribution as Record<string, number>)?.low || 0,
            },
          });
        }
      }

      // 【新增】处理agent询问消息 - 实时显示agent的问题
      if (event.next_question) {
        const existingMessages = useSessionStore.getState().messages;
        // 检查是否已经添加过这个消息（避免重复）
        const isDuplicate = existingMessages.some(
          (msg) => msg.role === 'assistant' && msg.content === event.next_question
        );
        if (!isDuplicate) {
          const assistantMessage: Message = {
            id: `msg-${Date.now()}-assistant-question`,
            role: 'assistant',
            content: event.next_question,
            timestamp: new Date().toISOString(),
          };
          addMessage(assistantMessage);
        }
      }
    },
    [
      setSessionId,
      setIncident,
      updateIncident,
      setFSMState,
      setFSMStates,
      setChecklist,
      setThinking,
      setReasoningSteps,
      setRiskAssessment,
      setSpatialAnalysis,
      setFlightImpact,
      addMessage,
      updateMessage,
      updateToolCall,
    ]
  );

  // 处理流式完成事件
  const handleStreamComplete = useCallback(
    (event: StreamEvent) => {
      // 最终更新
      handleStreamEvent(event);

      // 添加 Agent 响应消息 - 优先使用 final_answer（完整工单内容）
      const responseContent = event.final_answer || event.next_question;
      if (responseContent) {
        const assistantMessage: Message = {
          id: `msg-${Date.now()}-assistant`,
          role: 'assistant',
          content: responseContent,
          timestamp: new Date().toISOString(),
        };
        addMessage(assistantMessage);
      }

      // 添加完成系统消息
      const completeMessage: Message = {
        id: `msg-sys-complete-${Date.now()}`,
        role: 'system',
        content: `[完成] 处理结束，状态: ${event.status || 'completed'}`,
        timestamp: new Date().toISOString(),
      };
      addMessage(completeMessage);

      activeAbortController = null;
      setLoading(false);
      setThinking(false);
    },
    [handleStreamEvent, addMessage, setLoading, setThinking]
  );

  // 开始新会话
  const startSession = useCallback(
    async (scenarioId?: string) => {
      setLoading(true);
      resetSession();
      setDemoStep(0);

      try {
        if (demoMode) {
          // 演示模式使用 Mock 数据
          const result = await mockApi.startSession();
          if (result.success && result.data) {
            setSessionId(result.data.session_id);
            loadSession(result.data.state);
          }
        } else {
          // 在线模式调用真实 API
          const scenario = scenarioId
            ? presetScenarios.find((s) => s.id === scenarioId)
            : undefined;

          const result = await api.startSession({
            message: scenario?.initial_message || '',
            scenario_type: scenario?.scenario_type || '',
          });

          setSessionId(result.session_id);
          setFSMState(result.fsm_state as FSMState);
          if (result.fsm_states && result.fsm_states.length > 0) {
            setFSMStates(result.fsm_states);
          }
          if (result.incident) {
            setIncident(result.incident as Incident);
          }
          if (result.scenario_type) {
            const existingIncident = useSessionStore.getState().incident;
            if (existingIncident || result.incident) {
              updateIncident({ scenario_type: result.scenario_type as Incident['scenario_type'] });
            } else {
              setIncident({ scenario_type: result.scenario_type as Incident['scenario_type'] } as Incident);
            }
          }

          // 添加会话和场景系统消息
          const scenarioType = scenario?.scenario_type || result.scenario_type || '';
          const sysMessages: Message[] = [
            {
              id: `msg-sys-session-${Date.now()}`,
              role: 'system',
              content: `[信息] 会话 ID: ${result.session_id}`,
              timestamp: new Date().toISOString(),
            },
          ];
          if (scenarioType) {
            sysMessages.push({
              id: `msg-sys-scenario-${Date.now()}`,
              role: 'system',
              content: `[信息] 识别场景: ${scenarioLabels[scenarioType] || scenarioType}`,
              timestamp: new Date().toISOString(),
            });
          }
          sysMessages.forEach((msg) => addMessage(msg));

          // 转换 checklist 格式
          if (result.checklist) {
            const checklistItems: ChecklistItem[] = Object.entries(result.checklist).map(
              ([key, completed], index) => ({
                id: `check-${index}`,
                phase: 'P1' as const,
                item: key,
                completed: completed as boolean,
              })
            );
            setChecklist(checklistItems);
          }

          // 如果有风险等级
          if (result.risk_level) {
            setRiskAssessment({
              level: result.risk_level as RiskLevel,
              score: 0,
              factors: [],
              rules_triggered: [],
            });
          }

          // 添加 Agent 响应消息
          if (result.message) {
            const assistantMessage: Message = {
              id: `msg-${Date.now()}-assistant`,
              role: 'assistant',
              content: result.next_question || result.message,
              timestamp: new Date().toISOString(),
            };
            addMessage(assistantMessage);
          }
        }
      } catch (error) {
        setError(error instanceof Error ? error.message : '启动会话失败');
      } finally {
        setLoading(false);
      }
    },
    [
      demoMode,
      setLoading,
      resetSession,
      setSessionId,
      setIncident,
      setFSMState,
      setFSMStates,
      setChecklist,
      setRiskAssessment,
      addMessage,
      loadSession,
      setError,
    ]
  );

  // 发送消息 - 使用流式 API
  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return;

      // 取消之前的请求
      if (activeAbortController) {
        activeAbortController.abort();
        activeAbortController = null;
      }

      setLoading(true);
      setThinking(true, '正在分析...');
      // 注意：不再立即清空推理步骤，而是等待收到新的推理步骤时再更新
      // 这样可以避免在综合分析阶段界面突然变空的问题

      // 添加用户消息
      const userMessage: Message = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };
      addMessage(userMessage);

      try {
        if (demoMode) {
          // 演示模式逐步展示
          const result = await mockApi.chat(demoStep);

          if (result.success && result.data) {
            // 模拟工具调用过程
            if (result.data.tool_calls) {
              setToolCalls(result.data.tool_calls);
            }

            // 更新状态
            const state = result.data.state;
            if (state.incident) setIncident(state.incident);
            if (state.risk_assessment) setRiskAssessment(state.risk_assessment);
            if (state.spatial_analysis) setSpatialAnalysis(state.spatial_analysis);
            if (state.flight_impact) setFlightImpact(state.flight_impact);
            if (state.fsm_state) setFSMState(state.fsm_state);
            if (state.actions_taken) {
              state.actions_taken.forEach((action) => addAction(action));
            }
            if (state.checklist) {
              setChecklist(state.checklist);
            }

            // 添加助手消息
            if (state.messages) {
              const newMessages = state.messages.filter(
                (m) => m.role === 'assistant' && !messages.find((msg) => msg.id === m.id)
              );
              newMessages.forEach((m) => addMessage(m));
            }

            setDemoStep((prev) => prev + 1);
          }

          setLoading(false);
          setThinking(false);
        } else {
          // 在线模式 - 使用流式 API
          let currentSessionId = sessionId;

          if (!currentSessionId) {
            // 如果没有会话ID，使用流式启动
            activeAbortController = api.startSessionStream(
              {
                message: content,
                scenario_type: '',
              },
              {
                onNodeUpdate: handleStreamEvent,
                onComplete: handleStreamComplete,
                onError: (error) => {
                  setError(error instanceof Error ? error.message : (error as StreamEvent).error || '请求失败');
                  activeAbortController = null;
                  setLoading(false);
                  setThinking(false);
                },
              }
            );
          } else {
            // 继续对话 - 使用流式 API
            activeAbortController = api.chatStream(
              {
                session_id: currentSessionId,
                message: content,
              },
              {
                onNodeUpdate: handleStreamEvent,
                onComplete: handleStreamComplete,
                onError: (error) => {
                  setError(error instanceof Error ? error.message : (error as StreamEvent).error || '请求失败');
                  activeAbortController = null;
                  setLoading(false);
                  setThinking(false);
                },
              }
            );
          }
        }
      } catch (error) {
        setError(error instanceof Error ? error.message : '发送消息失败');
        setLoading(false);
        setThinking(false);
      }
    },
    [
      demoMode,
      demoStep,
      sessionId,
      messages,
      setLoading,
      setThinking,
      addMessage,
      setToolCalls,
      setReasoningSteps,
      setSessionId,
      setIncident,
      setRiskAssessment,
      setSpatialAnalysis,
      setFlightImpact,
      setFSMState,
      setChecklist,
      addAction,
      setError,
      handleStreamEvent,
      handleStreamComplete,
    ]
  );

  // 加载预设场景
  const loadPresetScenario = useCallback(
    async (scenarioId: string) => {
      const scenario = presetScenarios.find((s) => s.id === scenarioId);
      if (!scenario) return;

      if (demoMode) {
        await startSession(scenarioId);
        // 演示模式自动发送初始消息
        setTimeout(() => {
          sendMessage(scenario.initial_message);
        }, 500);
      } else {
        // 在线模式直接发送消息启动会话
        resetSession();
        await sendMessage(scenario.initial_message);
      }
    },
    [demoMode, startSession, sendMessage, resetSession]
  );

  const startSessionWithMessage = useCallback(
    async (scenarioType: string, content: string) => {
      if (!content.trim()) return;
      resetSession();
      setLoading(true);
      setThinking(true, '正在分析...');

      const userMessage: Message = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };
      addMessage(userMessage);

      try {
        activeAbortController = api.startSessionStream(
          {
            message: content,
            scenario_type: scenarioType,
          },
          {
            onNodeUpdate: handleStreamEvent,
            onComplete: handleStreamComplete,
            onError: (error) => {
              setError(error instanceof Error ? error.message : '请求失败');
              setLoading(false);
              setThinking(false);
              activeAbortController = null;
            },
          }
        );
      } catch (error) {
        setError(error instanceof Error ? error.message : '请求失败');
        setLoading(false);
        setThinking(false);
        activeAbortController = null;
      }
    },
    [
      resetSession,
      setLoading,
      setThinking,
      addMessage,
      handleStreamEvent,
      handleStreamComplete,
      setError,
    ]
  );

  // 取消当前请求
  const cancelRequest = useCallback(() => {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
    setLoading(false);
    setThinking(false);
  }, [setLoading, setThinking]);

  return {
    sessionId,
    messages,
    isLoading,
    isThinking,
    currentThinking,
    currentToolCalls,
    reasoningSteps,
    startSession,
    sendMessage,
    loadPresetScenario,
    startSessionWithMessage,
    resetSession,
    cancelRequest,
  };
}
