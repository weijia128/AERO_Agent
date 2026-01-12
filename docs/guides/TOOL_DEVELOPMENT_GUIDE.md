# 工具开发指南

本指南详细说明如何为 AERO Agent 系统创建新工具。

---

## 工具系统概述

工具是 Agent 执行具体操作的模块。AERO Agent 使用**工具注册模式**，所有工具继承 `BaseTool` 并注册到 `ToolRegistry`。

### 工具分类

```
tools/
├── base.py                  # BaseTool 基类
├── registry.py              # 工具注册中心
├── information/             # 信息查询类工具
│   ├── ask_for_detail.py   # 追问用户
│   ├── get_aircraft_info.py # 查询航班信息
│   └── smart_ask.py         # 智能批量询问
├── spatial/                 # 空间分析类工具
│   ├── get_stand_location.py # 机位查询
│   └── calculate_impact_zone.py # 影响区域计算
├── knowledge/               # 知识检索类工具
│   └── search_regulations.py # 规章检索
├── assessment/              # 评估类工具
│   └── assess_risk.py       # 风险评估
└── action/                  # 行动类工具
    ├── notify_department.py # 通知部门
    └── generate_report.py   # 生成报告
```

---

## 快速开始：创建你的第一个工具

### 示例：创建"获取天气"工具

**步骤 1**: 创建工具文件

```python
# tools/information/get_weather.py

from typing import Dict, Any
from tools.base import BaseTool

class GetWeatherTool(BaseTool):
    """
    获取指定位置的当前天气信息。

    用于评估天气对应急处置的影响（如风向对燃油扩散的影响）。
    """

    # 工具元数据
    name = "get_weather"
    description = (
        "获取当前天气条件（温度、风速、风向、降水）。"
        "当需要评估天气对事故处置的影响时使用此工具。"
    )

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具逻辑。

        Args:
            state: 当前 AgentState 字典
            inputs: LLM 提供的输入参数（来自 action_input 字段）

        Returns:
            包含以下键的字典：
                - observation: 返回给 Agent 的消息（字符串）
                - success: 布尔值，表示执行成功或失败
                - state_updates: (可选) 需要更新到 AgentState 的字段
        """
        # 1. 提取输入参数
        location = inputs.get("location")

        # 2. 验证输入
        if not location:
            return {
                "observation": "错误：缺少必需参数 'location'",
                "success": False
            }

        # 3. 执行核心逻辑
        try:
            weather_data = self._fetch_weather(location)

            # 4. 格式化返回消息
            observation = (
                f"{location}当前天气：\n"
                f"- 温度：{weather_data['temperature']}°C\n"
                f"- 风速：{weather_data['wind_speed']} m/s\n"
                f"- 风向：{weather_data['wind_direction']}\n"
                f"- 天气：{weather_data['conditions']}"
            )

            # 5. 返回结果
            return {
                "observation": observation,
                "success": True,
                "state_updates": {
                    "weather": weather_data  # 存入state供后续使用
                }
            }
        except Exception as e:
            return {
                "observation": f"获取天气失败：{str(e)}",
                "success": False
            }

    def _fetch_weather(self, location: str) -> Dict[str, Any]:
        """私有辅助方法：实际获取天气数据"""
        # 示例：调用天气API
        # 实际实现中应调用真实的天气服务
        return {
            "temperature": 25,
            "wind_speed": 5,
            "wind_direction": "东北",
            "conditions": "晴"
        }
```

**步骤 2**: 注册工具

```python
# tools/registry.py

from tools.information.get_weather import GetWeatherTool

def register_all_tools():
    """注册所有工具"""

    # ... 现有工具注册 ...

    # 注册天气工具
    ToolRegistry.register(
        GetWeatherTool(),
        scenarios=["oil_spill", "common"]  # 指定哪些场景可用
    )
```

**步骤 3**: 编写测试

```python
# tests/tools/test_get_weather.py

import pytest
from tools.information.get_weather import GetWeatherTool

class TestGetWeatherTool:
    def test_execute_success(self):
        """测试成功执行"""
        tool = GetWeatherTool()
        state = {"incident": {"position": "501"}}
        inputs = {"location": "成都天府国际机场"}

        result = tool.execute(state, inputs)

        assert result["success"] is True
        assert "温度" in result["observation"]
        assert "weather" in result.get("state_updates", {})

    def test_execute_missing_location(self):
        """测试缺少location参数"""
        tool = GetWeatherTool()
        state = {}
        inputs = {}  # 缺少location

        result = tool.execute(state, inputs)

        assert result["success"] is False
        assert "location" in result["observation"].lower()

    def test_execute_api_failure(self):
        """测试API调用失败"""
        tool = GetWeatherTool()
        tool._fetch_weather = lambda loc: (_ for _ in ()).throw(Exception("API Error"))

        state = {}
        inputs = {"location": "成都"}

        result = tool.execute(state, inputs)

        assert result["success"] is False
        assert "失败" in result["observation"]
```

**步骤 4**: 运行测试

```bash
pytest tests/tools/test_get_weather.py -v
```

---

## BaseTool 接口说明

### 必需实现的方法

```python
class YourTool(BaseTool):
    # 必需：工具名称（LLM用于选择工具）
    name: str = "your_tool_name"

    # 必需：工具描述（LLM用于理解工具用途）
    description: str = "Clear description of what this tool does and when to use it"

    # 必需：执行方法
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            state: 当前完整的 AgentState
            inputs: LLM 提供的参数

        Returns:
            {
                "observation": str,  # 必需
                "success": bool,     # 必需
                "state_updates": dict  # 可选
            }
        """
        pass
```

### 可选实现的方法

```python
class YourTool(BaseTool):
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """验证输入参数（可选）"""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """返回输入参数的JSON Schema（可选）"""
        pass
```

---

## 工具开发最佳实践

### 1. 清晰的命名

**好的命名**：
- `get_aircraft_info` - 动词开头，清晰意图
- `calculate_impact_zone` - 描述性
- `assess_risk` - 简洁明了

**不好的命名**：
- `tool1` - 无意义
- `process` - 太泛化
- `doStuff` - 不专业

### 2. 描述性的 description

```python
# 好的描述
description = (
    "获取航班的详细信息，包括航空公司、机型、起降时间、机位。"
    "当用户提供航班号时使用此工具。"
)

# 不好的描述
description = "Get flight info"  # 太简略
```

### 3. 输入验证

```python
def execute(self, state, inputs):
    # 必需参数验证
    required = ["param1", "param2"]
    missing = [p for p in required if p not in inputs]
    if missing:
        return {
            "observation": f"缺少必需参数：{', '.join(missing)}",
            "success": False
        }

    # 类型验证
    if not isinstance(inputs["param1"], str):
        return {
            "observation": "param1 必须是字符串",
            "success": False
        }

    # 范围验证
    if inputs["param2"] not in ["option1", "option2"]:
        return {
            "observation": "param2 必须是 option1 或 option2",
            "success": False
        }

    # ... 执行逻辑 ...
```

### 4. 错误处理

```python
def execute(self, state, inputs):
    try:
        result = self._do_something(inputs)
        return {
            "observation": f"成功：{result}",
            "success": True
        }
    except NetworkError as e:
        return {
            "observation": f"网络错误：{str(e)}",
            "success": False
        }
    except ValueError as e:
        return {
            "observation": f"参数错误：{str(e)}",
            "success": False
        }
    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return {
            "observation": f"工具执行失败：{str(e)}",
            "success": False
        }
```

### 5. 日志记录

```python
import logging
logger = logging.getLogger(__name__)

def execute(self, state, inputs):
    logger.info(f"Executing {self.name}", extra={"inputs": inputs})

    try:
        result = self._do_work(inputs)
        logger.debug(f"Tool result: {result}")
        return {"observation": result, "success": True}
    except Exception as e:
        logger.error(f"Tool failed: {e}", exc_info=True)
        return {"observation": str(e), "success": False}
```

### 6. 确定性优先

```python
# 好：确定性计算
def assess_risk(fluid_type, engine_status):
    if fluid_type == "FUEL" and engine_status == "RUNNING":
        return "HIGH"
    elif fluid_type == "HYDRAULIC":
        return "MEDIUM"
    return "LOW"

# 避免：在工具中使用LLM（增加不确定性）
def assess_risk_with_llm(fluid_type, engine_status):
    prompt = f"Assess risk for {fluid_type}, engine {engine_status}"
    return llm.call(prompt)  # 不推荐！
```

### 7. 幂等性

工具应该是幂等的，多次调用产生相同结果：

```python
# 好：每次调用结果一致
def get_stand_location(stand_id):
    return topology_graph.get_node(stand_id)

# 不好：有副作用
def notify_and_count(department):
    global notification_count
    notification_count += 1  # 副作用！
    send_notification(department)
```

---

## 高级功能

### 1. 状态更新

工具可以更新 AgentState：

```python
def execute(self, state, inputs):
    # ... 执行逻辑 ...

    return {
        "observation": "风险评估完成",
        "success": True,
        "state_updates": {
            "risk_assessment": {
                "level": "HIGH",
                "score": 90,
                "factors": ["航空燃油", "发动机运转"]
            },
            "mandatory_actions_done": {
                "risk_assessed": True  # 更新FSM标记
            }
        }
    }
```

### 2. 访问其他工具结果

```python
def execute(self, state, inputs):
    # 访问之前工具的结果
    risk_assessment = state.get("risk_assessment")
    if not risk_assessment:
        return {
            "observation": "请先执行风险评估",
            "success": False
        }

    risk_level = risk_assessment["level"]
    # ... 基于风险等级的逻辑 ...
```

### 3. 异步工具（规划中）

```python
import asyncio

class AsyncWeatherTool(BaseTool):
    async def execute_async(self, state, inputs):
        """异步执行方法"""
        weather_data = await self._fetch_weather_async(inputs["location"])
        return {
            "observation": f"Temperature: {weather_data['temp']}",
            "success": True
        }

    async def _fetch_weather_async(self, location):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.weather.com/{location}") as resp:
                return await resp.json()
```

---

## 工具测试指南

### 1. 单元测试结构

```python
class TestYourTool:
    @pytest.fixture
    def tool(self):
        """工具实例fixture"""
        return YourTool()

    @pytest.fixture
    def mock_state(self):
        """模拟状态fixture"""
        return {
            "incident": {...},
            "checklist": {...}
        }

    def test_success_case(self, tool, mock_state):
        """测试成功情况"""
        pass

    def test_missing_params(self, tool, mock_state):
        """测试缺少参数"""
        pass

    def test_invalid_params(self, tool, mock_state):
        """测试无效参数"""
        pass

    def test_external_api_failure(self, tool, mock_state, mocker):
        """测试外部API失败"""
        mocker.patch.object(tool, '_api_call', side_effect=Exception("API Error"))
        pass
```

### 2. 参数化测试

```python
@pytest.mark.parametrize("fluid_type,expected_risk", [
    ("FUEL", "HIGH"),
    ("HYDRAULIC", "MEDIUM"),
    ("OIL", "LOW"),
])
def test_risk_levels(tool, fluid_type, expected_risk):
    result = tool.execute({}, {"fluid_type": fluid_type})
    assert expected_risk in result["observation"]
```

### 3. Mock 外部依赖

```python
def test_with_mock_api(tool, mocker):
    # Mock 外部API调用
    mock_response = {"temperature": 25, "wind_speed": 5}
    mocker.patch.object(tool, '_fetch_weather', return_value=mock_response)

    result = tool.execute({}, {"location": "成都"})
    assert result["success"] is True
```

---

## 工具注册选项

### 场景特定工具

```python
# 仅漏油场景可用
ToolRegistry.register(AssessRiskTool(), scenarios=["oil_spill"])

# 仅鸟击场景可用
ToolRegistry.register(InspectAircraftTool(), scenarios=["bird_strike"])

# 所有场景可用
ToolRegistry.register(GetWeatherTool(), scenarios=["common"])
```

### 动态工具注册（高级）

```python
def register_tools_from_config(config_path: str):
    """从配置文件动态注册工具"""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    for tool_config in config["tools"]:
        tool_class = import_class(tool_config["class"])
        tool_instance = tool_class(**tool_config["params"])
        ToolRegistry.register(tool_instance, scenarios=tool_config["scenarios"])
```

---

## 常见问题

### Q: 工具执行失败时如何处理？

A: 工具应该返回 `success=False` 和清晰的错误消息。Agent 会将错误消息作为观察结果，并决定如何处理（重试、询问用户、使用其他工具等）。

### Q: 工具可以调用其他工具吗？

A: 不建议。工具应该是独立的原子操作。如果需要组合多个操作，让 Agent 通过 ReAct 推理来协调多个工具调用。

### Q: 工具的 description 有长度限制吗？

A: 建议 100-200 字符。太短LLM理解不清，太长会占用过多prompt空间。

### Q: 如何测试工具与 Agent 的集成？

A: 编写集成测试，模拟完整的对话流程：

```python
def test_weather_tool_integration():
    # 创建Agent
    agent = create_agent("oil_spill")

    # 模拟对话
    state = agent.run("501机位漏油，天气如何？")

    # 验证工具被调用
    assert "weather" in state
    assert state["weather"]["temperature"] is not None
```

---

## 相关文档

- [CLAUDE.md](../CLAUDE.md) - 完整开发指南
- [BaseTool API](../tools/base.py) - 基类源码
- [工具注册示例](../tools/registry.py) - 注册机制
- [测试示例](../tests/tools/) - 现有工具测试

---

**需要帮助？**

- 查看现有工具实现：`tools/information/get_aircraft_info.py`
- 参考测试用例：`tests/tools/test_assess_risk.py`
- 提出问题：GitHub Issues
