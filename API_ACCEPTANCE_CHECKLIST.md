# API 接口验收与测试清单（本地）

> 基础地址：`http://127.0.0.1:8001`
> 说明：多数接口需要鉴权头 `X-API-Key`（如环境未启用可省略）。

## 0. 健康检查

```bash
curl -s http://127.0.0.1:8001/health | python -m json.tool
```

## 1. 解析接口（不启动流程）

### 1.1 对外解析（产品层）
```bash
curl -s http://127.0.0.1:8001/analyze/parse \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{"message":"跑道11/29发现异物，疑似金属，仍在道面，请求支援"}' | python -m json.tool
```
验收点：返回 `scenario_type / incident / checklist / missing_fields`

### 1.2 内部解析（原生）
```bash
curl -s http://127.0.0.1:8001/event/parse \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{"message":"东航两幺四六报告燃油泄漏，发动机仍在运转，目前在机位217"}' | python -m json.tool
```
验收点：返回 `scenario_type / incident / checklist / enrichment_observation`

## 2. 一次性流式分析（对外产品层）

```bash
curl -N http://127.0.0.1:8001/analyze/start/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{"message":"东航两幺四六报告紧急情况，右侧发动机燃油持续泄漏，可见油迹扩散，发动机仍在运转，请求立即支援。目前在机位217"}'
```
验收点：
- 多个 `event: node_update`
- 最终 `event: complete` 包含 `recommendation` 且同时包含 `incident/checklist/risk_assessment`

## 3. 原生会话（非流式）

### 3.1 启动会话
```bash
curl -s http://127.0.0.1:8001/event/start \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{"message":"川航三两六洞滑行道L6液压油持续喷射，发动机运转中"}' | python -m json.tool
```
验收点：返回 `session_id` 与初始状态字段。

### 3.2 继续对话
```bash
curl -s http://127.0.0.1:8001/event/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{"session_id":"<session_id>","message":"在机位223，滑油泄漏持续滴漏"}' | python -m json.tool
```
验收点：返回更新后的 `fsm_state / risk_level / incident / checklist`。

### 3.3 获取会话状态
```bash
curl -s http://127.0.0.1:8001/event/<session_id> \
  -H "X-API-Key: <your_key>" | python -m json.tool
```

### 3.4 获取报告
```bash
curl -s http://127.0.0.1:8001/event/<session_id>/report \
  -H "X-API-Key: <your_key>" | python -m json.tool
```

### 3.5 获取报告（Markdown文件）
```bash
curl -L http://127.0.0.1:8001/event/<session_id>/report/markdown \
  -H "X-API-Key: <your_key>" -o report.md
```

### 3.6 关闭会话
```bash
curl -s -X DELETE http://127.0.0.1:8001/event/<session_id> \
  -H "X-API-Key: <your_key>" | python -m json.tool
```

## 4. 原生会话（流式）

### 4.1 流式启动
```bash
curl -N http://127.0.0.1:8001/event/start/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{"message":"厦航八两洞九报告滑油渗漏，发动机已关闭，在机位224"}'
```

### 4.2 流式继续对话
```bash
curl -N http://127.0.0.1:8001/event/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{"session_id":"<session_id>","message":"补充：泄漏面积不大，发动机已关闭"}'
```

## 5. 拓扑图层接口（地图数据）

```bash
curl -s http://127.0.0.1:8001/spatial/geojson/runway_surface \
  -H "X-API-Key: <your_key>" | head -n 3
```
可替换为：
- `runway_centerline` / `runway_label`
- `taxiway_surface` / `taxiway_centerline` / `taxiway_label`
- `stand_surface` / `stand_label`

---

## 常见验收要点
- 解析接口：能识别场景、抽取关键信息，并返回缺失字段。
- 流式接口：`node_update` 连续输出，`complete` 输出最终结果。
- 对外产品层：最终只给“处置意见 recommendation”，同时返回 `incident/checklist/risk_assessment` 作为依据。
