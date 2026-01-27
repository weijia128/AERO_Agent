# 前端交互优化实现总结

## 更新时间
2026-01-24

## 问题描述

用户报告了前端交互存在以下问题：
1. Agent询问消息未在前端显示（例如："东航2392，目前飞机的大概位置在哪？停机位还是滑行道？"）
2. 前端交互流程与终端不一致，缺少实时思考过程显示
3. 工单内容全部显示在对话界面，导致界面冗长
4. 推理过程中未显示工具调用详情

## 实现方案

### 1. Agent询问消息实时显示 ✅

**后端修改** (`apps/api/main.py:477-481`)
```python
# 提取agent询问消息（从messages中获取最新的assistant消息）
messages = state.get("messages", [])
for msg in reversed(messages):
    if msg.get("role") == "assistant":
        event["next_question"] = msg.get("content")
        break
```

**前端修改** (`frontend/src/hooks/useSession.ts:199-215`)
```typescript
// 处理agent询问消息 - 实时显示agent的问题
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
```

### 2. 终端风格交互流程 ✅

**ChatTimeline.tsx 完全重写** (512行)

#### 2.1 系统消息分类显示

创建 `SystemMessageBubble` 组件，根据消息类型使用不同颜色：
- 🎯 场景识别消息 - 蓝色 (`rgba(31, 111, 235, 0.1)`)
- 📝 实体提取消息 - 绿色 (`rgba(35, 134, 54, 0.1)`)
- ✈️ 航班计划消息 - 浅蓝色 (`rgba(88, 166, 255, 0.1)`)

```typescript
function SystemMessageBubble({ message, bigScreenMode }: MessageBubbleProps) {
  const isScenarioMessage = message.content.includes('[信息] 识别场景');
  const isExtractionMessage = message.content.includes('[信息] 本次提取');
  const isFlightPlanMessage = message.content.includes('[信息] 航班计划');
  // ... 根据类型设置不同的icon、bgColor、textColor
}
```

#### 2.2 推理步骤实时显示

创建 `ReasoningStepBubble` 组件，显示 [思考]、[执行]、[观察] 三部分：

```typescript
function ReasoningStepBubble({ step, bigScreenMode }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      {/* [思考] - 始终显示 */}
      <div style={{ background: 'rgba(251, 211, 141, 0.1)' }}>
        <BulbOutlined />
        <Text><strong>[思考]</strong> {step.thought}</Text>
      </div>

      {/* [执行] 和 [观察] - 可折叠 */}
      {expanded && (
        <div>
          {/* [执行] 工具调用 */}
          {step.action && (
            <div>
              <ToolOutlined />
              <Text>[执行] {step.action}</Text>
              {/* action_input 显示为 JSON */}
              <pre>{JSON.stringify(step.action_input, null, 2)}</pre>
            </div>
          )}

          {/* [观察] 工具返回结果 */}
          {step.observation && (
            <div>
              <EyeOutlined />
              <Text>[观察]</Text>
              <pre>{step.observation}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

#### 2.3 工单内容智能摘要

实现工单内容检测和摘要提取：

```typescript
// 检测是否为工单内容
function isReportContent(content: string): boolean {
  return (
    content.includes('## 机坪特情处置检查单') ||
    content.includes('# 机坪特情处置检查单') ||
    (content.includes('基本信息') && content.includes('风险评估') && content.includes('处置建议'))
  );
}

// 提取工单摘要（航班号、位置、风险等级等关键信息）
function extractReportSummary(content: string): string {
  const lines = content.split('\n');
  const summary: string[] = [];

  for (const line of lines) {
    if (line.includes('航班号') || line.includes('位置') ||
        line.includes('风险等级') || line.includes('油液类型')) {
      summary.push(line);
    }
    if (summary.length >= 6) break;
  }

  return summary.length > 0 ? summary.join('\n') :
    '工单已生成，包含基本信息、风险评估和处置建议';
}
```

**显示效果**：
- 默认显示：✅ 已生成工单模版 + 摘要（6行关键信息）
- 点击展开：完整工单内容（可滚动，最高400px）
- 点击收起：回到摘要视图

#### 2.4 消息渲染顺序

```typescript
export function ChatTimeline() {
  return (
    <>
      {/* 1. 渲染所有历史消息 */}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} bigScreenMode={bigScreenMode} />
      ))}

      {/* 2. 渲染当前推理步骤 */}
      {reasoningSteps.length > 0 && (
        <div>
          {reasoningSteps.map((step, stepIdx) => (
            <ReasoningStepBubble key={`step-${stepIdx}`} step={step} bigScreenMode={bigScreenMode} />
          ))}
        </div>
      )}

      {/* 3. 显示思考中状态 */}
      {isThinking && <div>💭 {currentThinking || '正在思考'}</div>}
    </>
  );
}
```

### 3. 拓扑地图高亮功能 ✅

#### 3.1 替换为 Plotly.js 可视化

**修改文件**:
- `frontend/src/components/visualization/TopologyMap.tsx` - 从582行简化到85行
- `frontend/public/topology_map.html` - 复制自原始 Plotly.js 可视化

**简化后的 TopologyMap 组件**:
```typescript
export function TopologyMap() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { incident, spatialAnalysis } = useSessionStore();

  useEffect(() => {
    if (iframeRef.current) {
      const params = new URLSearchParams();
      if (incident?.position) {
        params.set('incident', incident.position);
      }
      if (spatialAnalysis?.affected_stands?.length) {
        params.set('affected_stands', spatialAnalysis.affected_stands.join(','));
      }
      // ... 同样处理 affected_taxiways, affected_runways

      const newUrl = `/topology_map.html?${params.toString()}`;
      iframeRef.current.src = newUrl;
    }
  }, [incident?.position, spatialAnalysis]);

  return <iframe ref={iframeRef} src="/topology_map.html" />;
}
```

#### 3.2 URL参数动态高亮

**topology_map.html 增强功能**:
```javascript
// 读取URL参数
const urlParams = new URLSearchParams(window.location.search);
const incidentNode = urlParams.get('incident');
const affectedStands = urlParams.get('affected_stands')?.split(',').filter(Boolean) || [];
const affectedTaxiways = urlParams.get('affected_taxiways')?.split(',').filter(Boolean) || [];
const affectedRunways = urlParams.get('affected_runways')?.split(',').filter(Boolean) || [];

// 高亮机位
traces.forEach((trace, idx) => {
  if (trace.name === '机位') {
    const colors = trace.x.map((_, i) => {
      const nodeId = standNodes[i]?.id;
      if (nodeId === incidentNode) return '#DC143C'; // 深红色 - 事发位置
      if (affectedStands.includes(nodeId)) return '#FFA500'; // 橙色 - 受影响
      return '#FF6B6B'; // 默认红色
    });
    const sizes = trace.x.map((_, i) => {
      const nodeId = standNodes[i]?.id;
      if (nodeId === incidentNode) return 18; // 事发位置更大
      if (affectedStands.includes(nodeId)) return 14; // 受影响稍大
      return 10; // 默认大小
    });
    trace.marker = { ...trace.marker, color: colors, size: sizes };
  }
  // ... 同样处理跑道和滑行道
});
```

**高亮颜色方案**:
- 🔴 事发位置：深红色 (`#DC143C`)，尺寸18px
- 🟠 受影响机位：橙色 (`#FFA500`)，尺寸14px
- 🟡 受影响跑道/滑行道：金黄色 (`#FFD700`)，尺寸16px/8px

#### 3.3 状态显示框

在地图右上角显示当前高亮状态：
```javascript
if (incidentNode || affectedStands.length > 0 || ...) {
  const statusDiv = document.createElement('div');
  statusDiv.style.cssText = 'position: absolute; top: 20px; right: 20px; ...';

  let statusHTML = '<h4>📍 当前高亮状态</h4>';
  if (incidentNode) {
    statusHTML += '<div>🔴 事发位置: ' + incidentNode + '</div>';
  }
  if (affectedStands.length > 0) {
    statusHTML += '<div>🟠 受影响机位: ' + affectedStands.length + ' 个</div>';
  }
  // ...

  statusDiv.innerHTML = statusHTML;
  document.getElementById('graph').parentElement.appendChild(statusDiv);
}
```

#### 3.4 测试页面

创建 `frontend/public/topology_test.html` 包含4个测试场景：
1. 基础地图（无高亮）
2. 事发位置高亮（501机位）
3. 事发位置 + 受影响机位（501 + 502/503/504）
4. 完整影响范围（机位 + 滑行道 + 跑道）

### 4. 拓扑地图更新自动化 ✅

**创建脚本** `scripts/update_topology_map.py`:

```bash
# 用法
python scripts/update_topology_map.py <新拓扑HTML路径>

# 示例
python scripts/update_topology_map.py scripts/data_processing/topology_visualization_map_based.html
```

**功能**:
1. 复制新的拓扑HTML到 `frontend/public/topology_map.html`
2. 自动添加高亮功能代码（URL参数读取、节点高亮、状态显示）
3. 添加图例说明

**脚本核心函数**:
```python
def add_highlight_code(content: str) -> str:
    """添加高亮代码到HTML"""
    # 1. 添加URL参数读取和高亮逻辑
    highlight_code = '''...'''
    content = content.replace(
        "Plotly.newPlot('graph', traces, layout);",
        highlight_code + "Plotly.newPlot('graph', traces, layout);"
    )

    # 2. 添加状态显示框
    # 3. 添加图例说明
    return content
```

## 数据流架构

```
┌─────────────────────────────────────────────────────────────┐
│                         后端 (FastAPI)                       │
│                                                              │
│  LangGraph Agent → extract_stream_event() →                 │
│    ├─ next_question (agent问题)                             │
│    ├─ reasoning_steps (推理步骤)                             │
│    ├─ final_answer (工单内容)                                │
│    ├─ spatial_analysis (空间分析)                            │
│    └─ risk_assessment (风险评估)                             │
│                          ↓ SSE                               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────┐
│                   前端 (React + TypeScript)                  │
│                                                              │
│  useSession.ts (handleStreamEvent)                          │
│    ├─ next_question → addMessage()                          │
│    ├─ reasoning_steps → setReasoningSteps()                 │
│    ├─ spatial_analysis → setSpatialAnalysis()               │
│    └─ risk_assessment → setRiskAssessment()                 │
│                          ↓                                   │
│  sessionStore (Zustand)                                      │
│    ├─ messages[]                                             │
│    ├─ reasoningSteps[]                                       │
│    ├─ spatialAnalysis                                        │
│    └─ riskAssessment                                         │
│                          ↓                                   │
│  ChatTimeline.tsx                                            │
│    ├─ MessageBubble (用户/Agent消息)                         │
│    │   └─ 工单检测 → 摘要提取 + 可展开                       │
│    ├─ SystemMessageBubble (系统消息分类)                     │
│    ├─ ReasoningStepBubble (推理步骤)                         │
│    │   ├─ [思考] - 始终显示                                  │
│    │   └─ [执行]/[观察] - 可折叠                             │
│    └─ 思考中指示器                                           │
│                                                              │
│  TopologyMap.tsx (iframe)                                    │
│    └─ URL参数 → topology_map.html → Plotly.js高亮           │
└──────────────────────────────────────────────────────────────┘
```

## 文件修改清单

### 后端修改
- ✅ `apps/api/main.py` (第477-481行)
  - 添加 `next_question` 提取逻辑

### 前端修改
- ✅ `frontend/src/hooks/useSession.ts` (第199-215行)
  - 添加 `next_question` 实时显示处理

- ✅ `frontend/src/components/chat/ChatTimeline.tsx` (完全重写，512行)
  - 创建 `SystemMessageBubble` 组件
  - 创建 `ReasoningStepBubble` 组件
  - 实现 `isReportContent()` 和 `extractReportSummary()`
  - 修改 `MessageBubble` 添加工单特殊处理
  - 调整消息渲染顺序

- ✅ `frontend/src/components/visualization/TopologyMap.tsx` (从582行简化到85行)
  - 移除 ECharts 实现
  - 改用 iframe + URL 参数方案

### 新增文件
- ✅ `frontend/public/topology_map.html`
  - 复制自原始 Plotly.js 可视化
  - 添加 URL 参数读取
  - 添加节点高亮逻辑
  - 添加状态显示框
  - 添加图例说明

- ✅ `frontend/public/topology_test.html`
  - 4个测试场景
  - iframe 预览

- ✅ `scripts/update_topology_map.py`
  - 自动化拓扑地图更新
  - 代码注入（高亮、状态显示、图例）

- ✅ `docs/FRONTEND_FIXES_SUMMARY.md` (本文档)

## 测试验证

### 1. Agent询问消息测试
```bash
# 启动后端
cd /path/to/AERO_Agent
python -m apps.api.main

# 启动前端
cd frontend
npm run dev

# 测试场景
输入: "东航2392在501机位漏油"
预期: Agent询问 "东航2392，目前飞机的大概位置在哪？停机位还是滑行道？发动机当前状态？运转还是关车？"
```

### 2. 推理步骤显示测试
```bash
# 测试场景
输入: "CES2876在501机位漏油了"
预期:
- [思考] 部分始终显示
- [执行] 显示工具名称和参数（JSON格式）
- [观察] 显示工具返回结果
- 点击可折叠/展开详情
```

### 3. 工单摘要测试
```bash
# 测试场景
等待Agent生成完整工单
预期:
- 显示 "✅ 已生成工单模版"
- 显示摘要（航班号、位置、风险等级等关键信息）
- 点击 "查看完整工单 →" 展开
- 点击 "收起工单 ↑" 收起
```

### 4. 拓扑地图高亮测试
```bash
# 访问测试页面
http://localhost:5173/topology_test.html

# 测试4个场景
1. 基础地图（无高亮）
2. 事发位置高亮（501机位深红色）
3. 事发位置 + 受影响机位（501深红 + 502/503/504橙色）
4. 完整影响范围（机位 + 滑行道 + 跑道全部高亮）

# 验证
- ✅ 节点颜色正确
- ✅ 节点尺寸正确
- ✅ 右上角状态框显示
- ✅ 图例说明显示
```

### 5. TypeScript 类型检查
```bash
cd frontend
npx tsc --noEmit
# 输出: TypeScript 类型检查通过 ✅
```

## 实现效果对比

### 修改前
- ❌ Agent询问消息不显示
- ❌ 无推理过程实时显示
- ❌ 工单内容全部显示，界面冗长
- ❌ 无工具调用详情
- ❌ 拓扑地图为 ECharts 实现，无高亮功能

### 修改后
- ✅ Agent询问消息实时显示（无重复）
- ✅ 推理步骤实时显示 [思考]/[执行]/[观察]
- ✅ 工单内容智能摘要，可展开查看
- ✅ 工具调用详情完整显示（名称、参数、结果）
- ✅ 拓扑地图 Plotly.js 实现，支持 URL 参数高亮
- ✅ 系统消息分类显示（场景/提取/航班）
- ✅ 完全匹配终端交互流程

## 性能优化

1. **避免重复消息**: `next_question` 处理中添加重复检测
2. **按需渲染**: 推理步骤的执行/观察部分默认折叠
3. **工单内容懒加载**: 默认只显示摘要，点击后才渲染完整内容
4. **iframe 隔离**: 拓扑地图在 iframe 中独立运行，不影响主应用性能

## 后续优化建议

1. **推理步骤持久化**: 当前 reasoningSteps 在刷新后丢失，可考虑持久化到 sessionStorage
2. **工单模板配置化**: extractReportSummary 中的关键词可以配置化
3. **拓扑地图交互增强**: 添加节点点击事件，显示详细信息
4. **消息搜索功能**: 添加消息搜索和过滤功能
5. **导出功能**: 支持导出对话记录和工单内容为 PDF/Markdown

## 开发者注意事项

### 添加新的系统消息类型
在 `ChatTimeline.tsx` 的 `SystemMessageBubble` 中添加：
```typescript
const isYourNewType = message.content.includes('[信息] 你的标识');
if (isYourNewType) {
  icon = <span>🆕</span>;
  bgColor = 'rgba(xxx, xxx, xxx, 0.1)';
  textColor = '#xxxxxx';
}
```

### 修改工单检测逻辑
在 `ChatTimeline.tsx` 的 `isReportContent` 函数中添加新的检测条件：
```typescript
function isReportContent(content: string): boolean {
  return (
    content.includes('## 机坪特情处置检查单') ||
    content.includes('你的新标识') // 添加这里
  );
}
```

### 更新拓扑地图
```bash
# 1. 生成新的拓扑HTML
python scripts/your_topology_generator.py

# 2. 自动更新到前端
python scripts/update_topology_map.py path/to/new_topology.html

# 3. 刷新浏览器查看效果
```

## 相关文档

- [CLAUDE.md](../CLAUDE.md) - 项目总体架构
- [FRONTEND_DEMO_PLAN.md](../FRONTEND_DEMO_PLAN.md) - 前端优化计划
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - API文档

## 版本历史

- **v1.0** (2026-01-24)
  - 完成 Agent 询问消息实时显示
  - 完成终端风格交互流程
  - 完成拓扑地图高亮功能
  - 完成拓扑地图更新自动化
