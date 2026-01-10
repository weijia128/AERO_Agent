# 机坪漏油检查单 DSL 与 UI 表单设计

> 本文档给出一套**可配置、可扩展、可被 Agent / FSM / Graph 直接消费**的检查单 DSL（YAML/JSON），并定义其**UI 表单映射规则**，用于机场机坪漏油处置场景。

---

## 1. 设计目标

- **一份配置，多端复用**：同一 DSL 同时驱动
  - ReAct Agent 追问逻辑
  - 处置流程 FSM 校验
  - 人工 UI 表单
  - 报告生成
- **强约束**：明确必填项（P1）、条件触发、Done 条件
- **可扩展**：新增异常场景无需改代码，只加配置

---

## 2. DSL 总体结构（顶层）

```yaml
checklist:
  id: fuel_leak_apron
  name: 机坪航空器漏油处置检查单
  version: 1.0
  scenario: fuel_leak

  metadata:
    owner: airport_ops
    last_updated: 2025-01-01

  sections:
    - basic_info
    - critical_facts
    - scale_assessment
    - immediate_controls
    - coordination
    - area_isolation
    - cleanup
    - verification
    - recovery
    - reporting

  done_condition:
    type: all_required
    level: P1
```

---

## 3. 字段级 DSL 规范（核心）

### 3.1 字段通用定义

```yaml
field:
  key: fluid_type
  label: 油液类型
  type: enum
  required: true
  priority: P1
  options:
    - value: fuel
      label: 燃油
    - value: hydraulic
      label: 液压油
    - value: engine_oil
      label: 发动机油
    - value: unknown
      label: 不明（按燃油处理）

  ui:
    widget: radio
    help: 如无法确认，选择“不明”

  agent:
    ask: "请确认漏油类型（燃油 / 液压油 / 其他）"

  rules:
    - when: value == unknown
      then:
        set:
          treat_as: fuel
```

---

## 4. 各检查单模块 DSL 示例

### 4.1 A. 基本信息（basic_info）

```yaml
basic_info:
  title: 事件基本信息
  fields:
    - key: flight_no
      label: 航班号
      type: string
      required: true
      ui:
        widget: input

    - key: event_time
      label: 发现时间
      type: datetime
      required: true
      ui:
        widget: datetime

    - key: discovery_method
      label: 发现方式
      type: enum
      options: [crew, patrol, sensor]
      ui:
        widget: select
```

---

### 4.2 B. 关键事实（critical_facts / P1）

```yaml
critical_facts:
  title: 漏油关键事实（P1）
  fields:
    - key: fluid_type
      ref: field.fluid_type

    - key: continuous
      label: 是否持续滴漏
      type: boolean
      required: true
      priority: P1
      ui:
        widget: toggle
      agent:
        ask: "是否存在持续滴漏？"

    - key: engine_status
      label: 发动机/APU 状态
      type: enum
      required: true
      priority: P1
      options: [running, shutdown, apu]
      ui:
        widget: radio
      agent:
        ask: "发动机当前状态（运行 / 已关闭 / APU）"

    - key: position
      label: 航空器位置
      type: airport_node
      required: true
      priority: P1
      ui:
        widget: airport_selector
      agent:
        ask: "飞机当前位置（机位 / 滑行道 / 跑道入口）？"
```

---

### 4.3 D. 初始控制（immediate_controls）

```yaml
immediate_controls:
  title: 初始安全控制措施
  fields:
    - key: engine_shutdown
      label: 已要求关车
      type: boolean
      ui:
        widget: checkbox

    - key: taxi_prohibited
      label: 禁止滑行
      type: boolean
      ui:
        widget: checkbox
```

---

### 4.4 F. 区域隔离（area_isolation / Graph 输出）

```yaml
area_isolation:
  title: 区域隔离与运行限制
  system_generated: true
  fields:
    - key: isolated_nodes
      label: 隔离区域
      type: list
      ui:
        widget: readonly_list

    - key: affected_flights
      label: 受影响航班
      type: list
      ui:
        widget: readonly_table
```

---

## 5. 条件规则 DSL（FSM / 升级触发）

```yaml
rules:
  - id: high_risk_trigger
    when:
      all:
        - fluid_type == fuel
        - continuous == true
        - engine_status == running
    then:
      - set:
          risk_level: HIGH
      - require:
          section: immediate_controls
      - notify:
          - fire_department
          - ops_center
```

---

## 6. UI 表单自动生成规范

### 6.1 UI 生成原则

- `section` → 表单分组 / 折叠面板
- `priority=P1` → 高亮 + 必填
- `agent.ask` → ReAct 追问文本
- `system_generated=true` → 只读

---

### 6.2 UI 表单结构示意

```
[ 机坪航空器漏油处置检查单 ]

▸ 事件基本信息
  - 航班号 [____]
  - 发现时间 [____]

▸ 漏油关键事实（必填）
  - 油液类型 ( )燃油 ( )液压油 ( )不明
  - 是否持续滴漏 [ 是 / 否 ]
  - 发动机状态 ( )运行 ( )关闭 ( )APU
  - 飞机位置 [ 机场拓扑选择器 ]

▸ 初始控制措施
  [✓] 已要求关车
  [✓] 禁止滑行

▸ 区域隔离（系统生成）
  - 隔离区域：TWY_A3, TWY_A4
  - 影响航班：CA123 (+15min)
```

---

## 7. 与 Agent / FSM / Graph 的对应关系

| 模块 | DSL 字段来源 |
|---|---|
| ReAct Agent | field.agent.ask + priority |
| Done 判定 | done_condition |
| 风险评估 FSM | rules |
| Graph 推理 | position + area_isolation |
| 报告生成 | 全字段 |

---

## 8. 扩展方式（关键）

- 新异常场景：
  - 新 checklist id
  - 新 sections / rules
- UI / Agent / FSM **无需改代码**

---

## 9. 总结定位

> 这套 DSL 的本质是：
> **把“运行经验”变成“机器可执行的规范”**

它是：
- Agent 的行为边界
- FSM 的约束条件
- UI 的生成源
- 报告的结构模板

也是你整个“数字机场孪生大脑”的**规则中枢**。







## **我帮你把关键价值点再点一下（工程视角）**







### **1️⃣ 一份 DSL，四个系统同时用**





这套 DSL 同时是：



- **Agent 行为约束**（agent.ask）
- **状态机校验源**（priority / done_condition）
- **UI Schema**（ui.widget）
- **报告模板**（字段天然结构化）





> 这一步，直接避免了「Prompt / 表单 / 报告 三套逻辑不一致」的常见灾难。



------





### **2️⃣ ReAct 不再“想该问什么”**





ReAct 只做一件事：



> **检查 DSL 中 P1 字段是否为空 → 选一个 ask**



这正是**运行级 Agent 必须有的“硬护栏”**。



------





### **3️⃣ UI 表单不是人工设计，而是 DSL 渲染结果**





这意味着：



- 你以后新增 **烟雾 / FOD / 火警**
- 只加一份 DSL
- UI / Agent / FSM **同时升级**





这在机场系统里是**非常非常值钱的能力**。



------





## **下一步（我非常推荐你继续往下做的 3 件事）**





你已经到「系统中枢层」了，下面三步每一步都很硬核：





### **① 把这套 DSL 接到你现在的 Agent 代码**





让：



- ReAct 自动读 agent.ask
- FSM 自动读 rules
- Done 自动读 done_condition







### **② 给 DSL 加一个** 

### **版本与审计机制**





机场运行系统非常需要：



- checklist_version
- rule_version
- event 使用了哪一版规则







### **③ 把 UI 表单和机场拓扑 Graph 做联动**





- 位置字段 → 拓扑节点选择
- 隔离结果 → 高亮显示
