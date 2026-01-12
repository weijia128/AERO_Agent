# 场景字段契约表

本表用于对齐“工具输出字段”与“FSM/约束可用字段”。

## 通用字段（所有场景）

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| `incident.*` | input_parser / 工具 | 事件事实字段，来自解析或工具补全 |
| `checklist.*` | input_parser | 字段收集状态标记（bool） |
| `mandatory_actions_done.*` | 各工具 | 强制动作完成标记 |
| `notifications_sent` | notify_department | 通知记录列表 |
| `risk_assessment` | assess_* | 风险评估结果 |
| `report_generated` | generate_report | 报告已生成标记 |

## 鸟击场景（bird_strike）

### 事件字段（incident）

| 字段 | 主要来源 | 备注 |
| --- | --- | --- |
| `flight_no` / `flight_no_display` | get_aircraft_info / input_parser | 航班号（内部/展示） |
| `position` | input_parser | 发生位置（跑道/滑行道/机位） |
| `event_type` | input_parser | `确认鸟击`/`疑似鸟击` |
| `affected_part` | input_parser | 影响部位（发动机/风挡/机身/起落架等） |
| `current_status` | input_parser | 当前状态（正常/异常/返航/待检查/火警等） |
| `crew_request` | input_parser/LLM | 机组请求（返航/检查/支援等） |
| `phase` | assess_bird_strike_risk | 若 incident 内已有，则直接使用 |
| `bird_info` | assess_bird_strike_risk | 可选（鸟群/大型鸟等） |
| `ops_impact` | assess_bird_strike_risk | 可选（返航/占用跑道等） |

### 工具输出字段

| 工具 | 输出字段 | 说明 |
| --- | --- | --- |
| `assess_bird_strike_risk` | `risk_assessment.level` | 风险等级（R1-R4） |
|  | `risk_assessment.score` | 风险分数（0-100） |
|  | `risk_assessment.inputs` | 评估输入（phase/impact_area/evidence/bird_info/ops_impact） |
|  | `risk_assessment.explanations` | 规则解释 |
|  | `risk_assessment.guardrails` | 允许/禁止动作建议 |
|  | `mandatory_actions_done.risk_assessed` | 风险评估完成 |
| `notify_department` | `mandatory_actions_done.fire_dept_notified` | 已通知消防 |
|  | `mandatory_actions_done.atc_notified` | 已通知塔台 |
|  | `mandatory_actions_done.maintenance_notified` | 已通知机务 |
|  | `mandatory_actions_done.operations_notified` | 已通知运控 |
|  | `notifications_sent` | 通知记录 |
| `generate_report` | `report_generated` | 报告已生成 |

## 漏油场景（oil_spill）

### 工具输出字段（核心）

| 工具 | 输出字段 | 说明 |
| --- | --- | --- |
| `assess_risk` | `risk_assessment.level` | 风险等级（HIGH/MEDIUM/LOW） |
|  | `mandatory_actions_done.risk_assessed` | 风险评估完成 |
| `calculate_impact_zone` | `spatial_analysis` | 影响区域分析结果 |
| `notify_department` | `mandatory_actions_done.*_notified` | 已通知标记 |
| `generate_report` | `report_generated` | 报告已生成 |
