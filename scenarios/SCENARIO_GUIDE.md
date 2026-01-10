# 场景创建指南

## 目录结构

每个场景一个目录，包含以下文件：

```
scenarios/
├── base.py                    # 场景基类和注册中心
├── oil_spill/                 # 漏油场景
│   ├── config.yaml           # 主配置
│   ├── checklist.yaml        # Checklist 配置
│   ├── fsm_states.yaml       # FSM 状态机配置
│   └── prompt.yaml           # System Prompt 配置 ⭐ 新增
├── bird_strike/              # 鸟击场景 ⭐ 示例
│   └── prompt.yaml           # 只需要 prompt.yaml
└── fod/                       # FOD 场景 ⭐ 可扩展
    └── prompt.yaml
```

## prompt.yaml 文件结构

```yaml
# 场景 System Prompt
system_prompt: |
  你是机场[场景名]专家 Agent...
  # ... 完整的 system prompt

# 字段收集顺序（用于 checklist 显示）
field_order:
  - field_key_1
  - field_key_2
  - field_key_3

# 字段中文名称映射
field_names:
  field_key_1: 字段1中文名
  field_key_2: 字段2中文名

# 字段追问提示
ask_prompts:
  field_key_1: "请提供...？"
  field_key_2: "请确认...？"

# 风险等级定义
risk_levels:
  HIGH:
    description: "高风险描述"
    color: "red"
  MEDIUM:
    description: "中风险描述"
    color: "yellow"
  LOW:
    description: "低风险描述"
    color: "green"

# 强制动作触发规则
mandatory_actions:
  - when:
      some_field: some_value
    action: tool_name
    params:
      key: value
```

## 添加新场景步骤

### 1. 创建场景目录

```bash
mkdir -p scenarios/new_scenario
```

### 2. 创建 prompt.yaml

参考 `scenarios/oil_spill/prompt.yaml` 或 `scenarios/bird_strike/prompt.yaml`

### 3. 注册场景（可选）

如果需要自定义逻辑，在 `scenarios/base.py` 中添加场景类：

```python
class NewScenario(BaseScenario):
    name = "new_scenario"
    version = "1.0"
    prompt_path = Path(__file__).parent / "new_scenario" / "prompt.yaml"

    def get_tools(self) -> List[str]:
        return ["tool1", "tool2", ...]

# 注册
ScenarioRegistry.register(NewScenario())
```

### 4. 使用场景

在启动 Agent 时指定场景类型：

```python
from agent.state import create_initial_state

state = create_initial_state(
    session_id="xxx",
    scenario_type="new_scenario",  # 使用新场景
    initial_message="报告事件...",
)
```

## 现有场景

| 场景 | 状态 | 说明 |
|------|------|------|
| oil_spill | ✅ 完整 | 机坪漏油场景，完整配置 |
| bird_strike | ⭐ 示例 | 鸟击场景，仅 prompt 配置 |

## 扩展场景示例

### FOD（机场道面外来物）

```yaml
system_prompt: |
  你是机场 FOD 巡检专家 Agent。你的任务是处理道面外来物报告...

field_order:
  - position
  - fod_type
  - size
  - threat_level

field_names:
  position: 发现位置
  fod_type: 异物类型
  size: 尺寸大小
  threat_level: 威胁等级
```
