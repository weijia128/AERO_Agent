# API 文档

**基础 URL**: `http://localhost:8000` (本地开发)
**版本**: v1
**协议**: HTTP/REST
**格式**: JSON

---

## 认证

⚠️ **当前状态**: 无认证（开发中）
🔜 **规划**: API 密钥认证（阶段2）

---

## 端点概览

| 方法 | 端点 | 描述 | 状态 |
|------|------|------|------|
| POST | `/event/start` | 创建新事件会话 | ✅ |
| POST | `/event/chat` | 继续对话 | ✅ |
| GET | `/event/{session_id}` | 获取会话状态 | ✅ |
| GET | `/event/{session_id}/report` | 获取生成的报告 | ✅ |
| DELETE | `/event/{session_id}` | 关闭会话 | ✅ |

---

## 详细端点说明

### 1. 创建新事件会话

**端点**: `POST /event/start`

**描述**: 创建一个新的应急响应会话。

**请求体**:
```json
{
  "scenario_type": "oil_spill",
  "initial_message": "501机位发现燃油泄漏"
}
```

**参数**:
- `scenario_type` (string, optional): 场景类型，默认 "oil_spill"
  - 可选值: `"oil_spill"`, `"bird_strike"`
- `initial_message` (string, optional): 初始消息

**响应** (200 OK):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "事件会话已创建",
  "agent_response": "天府机坪，请讲。"
}
```

**Curl 示例**:
```bash
curl -X POST http://localhost:8000/event/start \
  -H "Content-Type: application/json" \
  -d '{"scenario_type": "oil_spill", "initial_message": "501机位发现燃油泄漏"}'
```

---

### 2. 继续对话

**端点**: `POST /event/chat`

**描述**: 向现有会话发送消息并获取 Agent 响应。

**请求体**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "南航3456，持续滴漏，发动机运转中"
}
```

**参数**:
- `session_id` (string, required): 会话 ID
- `message` (string, required): 用户消息

**响应** (200 OK):
```json
{
  "agent_response": "南航3456，收到。请问具体位置？",
  "state": {
    "scenario_type": "oil_spill",
    "is_complete": false,
    "checklist": {
      "flight_no": true,
      "continuous": true,
      "engine_status": true,
      "fluid_type": false,
      "position": false
    }
  }
}
```

**Curl 示例**:
```bash
curl -X POST http://localhost:8000/event/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "550e8400-...", "message": "南航3456，持续滴漏"}'
```

---

### 3. 获取会话状态

**端点**: `GET /event/{session_id}`

**描述**: 获取会话的当前状态。

**路径参数**:
- `session_id` (string): 会话 ID

**响应** (200 OK):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "scenario_type": "oil_spill",
  "created_at": "2024-01-15T10:30:00Z",
  "is_complete": false,
  "fsm_state": "P1_RISK_ASSESS",
  "checklist": {
    "flight_no": true,
    "position": true,
    "fluid_type": true,
    "engine_status": true,
    "continuous": true
  },
  "incident": {
    "flight_no": "CZ3456",
    "position": "501",
    "fluid_type": "FUEL",
    "engine_status": "RUNNING",
    "continuous": true
  },
  "risk_assessment": {
    "level": "HIGH",
    "score": 90,
    "factors": ["航空燃油", "发动机运转", "持续滴漏"]
  }
}
```

**Curl 示例**:
```bash
curl http://localhost:8000/event/550e8400-e29b-41d4-a716-446655440000
```

---

### 4. 获取报告

**端点**: `GET /event/{session_id}/report`

**描述**: 获取生成的事件报告（仅在会话完成后可用）。

**路径参数**:
- `session_id` (string): 会话 ID

**响应** (200 OK):
```json
{
  "report": {
    "title": "机坪应急响应检查单",
    "timestamp": "2024-01-15T11:00:00Z",
    "summary": "...",
    "risk_level": "HIGH",
    "handling_process": [...],
    "recommendations": [...]
  },
  "markdown": "# 机坪应急响应检查单\n\n..."
}
```

**响应** (404 Not Found) - 报告未生成:
```json
{
  "detail": "报告尚未生成"
}
```

**Curl 示例**:
```bash
curl http://localhost:8000/event/550e8400-e29b-41d4-a716-446655440000/report
```

---

### 5. 关闭会话

**端点**: `DELETE /event/{session_id}`

**描述**: 关闭并删除会话。

**路径参数**:
- `session_id` (string): 会话 ID

**响应** (200 OK):
```json
{
  "message": "会话已关闭"
}
```

**响应** (404 Not Found):
```json
{
  "detail": "会话不存在"
}
```

**Curl 示例**:
```bash
curl -X DELETE http://localhost:8000/event/550e8400-e29b-41d4-a716-446655440000
```

---

## 错误响应

所有端点可能返回以下错误：

### 400 Bad Request
```json
{
  "detail": "Invalid request: missing required field 'message'"
}
```

### 404 Not Found
```json
{
  "detail": "会话不存在"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error",
  "error_id": "err_xyz123"  // 仅在 DEBUG=false 时
}
```

在 `DEBUG=true` 模式下，500 错误会包含完整追踪：
```json
{
  "detail": "LLM API call failed: Connection timeout",
  "traceback": "Traceback (most recent call last):\n  ..."
}
```

⚠️ **生产环境**: 应设置 `DEBUG=false` 以避免暴露敏感信息。

---

## 数据模型

### AgentState (简化版)

```typescript
interface AgentState {
  session_id: string;
  scenario_type: string;
  created_at: string;
  is_complete: boolean;
  fsm_state: string;

  // 核心数据
  incident: IncidentInfo;
  checklist: ChecklistStatus;
  risk_assessment?: RiskAssessment;
  spatial_analysis?: SpatialAnalysis;

  // 对话历史
  messages: Message[];

  // 报告
  final_report?: FinalReport;
  final_answer?: string;
}
```

### IncidentInfo

```typescript
interface IncidentInfo {
  flight_no?: string;
  position?: string;
  fluid_type?: "FUEL" | "HYDRAULIC" | "OIL";
  engine_status?: "RUNNING" | "OFF";
  continuous?: boolean;
  leak_size?: "LARGE" | "MEDIUM" | "SMALL";
}
```

### RiskAssessment

```typescript
interface RiskAssessment {
  level: "HIGH" | "MEDIUM_HIGH" | "MEDIUM" | "LOW";
  score: number;  // 0-100
  factors: string[];
  immediate_actions: string[];
}
```

---

## 完整工作流示例

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. 创建会话
response = requests.post(f"{BASE_URL}/event/start", json={
    "scenario_type": "oil_spill",
    "initial_message": "501机位发现燃油泄漏"
})
session_id = response.json()["session_id"]
print(f"会话ID: {session_id}")

# 2. 多轮对话
messages = [
    "南航3456，持续滴漏",
    "发动机还在运转",
    "在501机位"
]

for msg in messages:
    response = requests.post(f"{BASE_URL}/event/chat", json={
        "session_id": session_id,
        "message": msg
    })
    agent_response = response.json()["agent_response"]
    print(f"Agent: {agent_response}")

# 3. 检查状态
response = requests.get(f"{BASE_URL}/event/{session_id}")
state = response.json()
print(f"FSM状态: {state['fsm_state']}")
print(f"风险等级: {state.get('risk_assessment', {}).get('level')}")

# 4. 获取报告（如果已生成）
response = requests.get(f"{BASE_URL}/event/{session_id}/report")
if response.status_code == 200:
    report = response.json()["markdown"]
    print(report)

# 5. 关闭会话
requests.delete(f"{BASE_URL}/event/{session_id}")
```

---

## 速率限制

⚠️ **当前状态**: 无速率限制
🔜 **规划**: 每 IP 100 请求/分钟（阶段2）

---

## WebSocket 支持

🔜 **规划中**: 实时流式响应

```javascript
// 未来 API (规划)
const ws = new WebSocket('ws://localhost:8000/ws/event');

ws.on('message', (data) => {
  const event = JSON.parse(data);
  if (event.type === 'agent_response_chunk') {
    console.log(event.content);
  }
});
```

---

## 更新日志

### v1.0 (当前)
- ✅ 基本 REST API
- ✅ 会话管理
- ✅ 多轮对话
- ✅ 报告生成

### v1.1 (规划)
- 🔜 API 密钥认证
- 🔜 速率限制
- 🔜 健康检查端点
- 🔜 Prometheus 指标

### v2.0 (未来)
- 🔜 WebSocket 流式响应
- 🔜 批量会话操作
- 🔜 会话导出/导入
- 🔜 OpenAPI/Swagger UI

---

## 相关文档

- [部署指南](./DEPLOYMENT_GUIDE.md) - 生产部署配置
- [CLAUDE.md](../CLAUDE.md) - 开发者指南
- [生产就绪度评估](./PRODUCTION_READINESS.md) - 当前限制
