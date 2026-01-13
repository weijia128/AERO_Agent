# get_weather 工具集成文档

## 概述

`get_weather` 工具已成功集成到AERO Agent系统中，允许Agent查询机场实时气象数据，包括温度、风速、气压、能见度等信息。

## 功能特性

### 支持的查询方式

1. **按位置查询**: 查询特定位置的最新气象数据
2. **按时间查询**: 查询特定时刻的气象数据
3. **自动选择**: 根据事件位置自动选择最近的气象观测点

### 支持的位置

| 类型 | 位置ID |
|------|--------|
| 跑道端 | 05L, 05R, 06L, 06R, 23L, 23R, 24L, 24R |
| 区域 | NORTH, SOUTH |

### 返回的气象数据

| 字段 | 说明 | 单位 |
|------|------|------|
| temperature | 温度 | °C |
| dew_point | 露点 | °C |
| relative_humidity | 相对湿度 | % |
| wind_direction | 风向 | 度 |
| wind_speed | 风速 | m/s |
| wind_speed_10m | 10米高度风速 | m/s |
| qnh | QNH气压 | hPa |
| visibility | 能见度 | m |

## 使用方法

### 在Agent对话中使用

Agent会自动识别查询气象信息的意图并调用工具：

```
User: 查询05L跑道当前的天气情况
Agent: 【调用get_weather工具】
【05L 气象信息】
观测时间: 23:59:58
🌬️  风: 278° 2.3 m/s
   (轻风)
```

### Python代码中直接使用

```python
from tools.information.get_weather import GetWeatherTool

tool = GetWeatherTool()
state = {"incident": {}}

# 查询05L位置的气象
result = tool.execute(state, {"location": "05L"})
print(result["observation"])

# 访问结构化数据
if "weather" in result:
    weather = result["weather"]
    print(f"温度: {weather['temperature']}°C")
    print(f"风速: {weather['wind_speed']} m/s")
```

### 高级用法

```python
# 查询特定时间的气象
result = tool.execute(
    state,
    {
        "location": "05L",
        "timestamp": "2026-01-06 05:30:00"
    }
)

# 自动选择观测点（推荐用于应急场景）
state = {"incident": {"position": "501"}}
result = tool.execute(state, {"location": "推荐"})
```

## 工作原理

### 数据流程

```
AWOS日志文件
    ↓
extract_awos_weather.py (提取并清洗)
    ↓
awos_weather_*.csv (存储在 data/processed/)
    ↓
get_weather tool (查询)
    ↓
格式化输出给Agent/用户
```

### 时间匹配逻辑

工具使用**最近邻匹配**算法：

1. 如果指定了时间戳，查找最接近该时间的记录
2. 如果未指定时间，返回数据中最新的记录
3. 如果时间差超过1小时，认为数据不相关，返回None

### 位置映射

当使用`location="推荐"`时，工具会根据事件位置自动选择观测点：

```python
position_to_sensor = {
    "501": "05L",  # 501机位 -> 05L跑道观测点
    "601": "06L",  # 601机位 -> 06L跑道观测点
    # 其他默认使用NORTH
}
```

## 数据准备

### 第一步：提取气象数据

```bash
python scripts/data_processing/extract_awos_weather.py
```

输出：`data/processed/awos_weather_<timestamp>.csv`

### 第二步：（可选）分析数据

```bash
python scripts/data_processing/analyze_awos_weather.py
```

输出：
- `awos_analysis_report_*.txt` - 分析报告
- `awos_per_location/` - 按位置分离的CSV

### 第三步：（可选）导出Excel

```bash
python scripts/data_processing/export_awos_to_excel.py
```

输出：`awos_weather_*.xlsx`（包含清洗后的数据）

## 演示脚本

运行完整演示：

```bash
python demos/demo_get_weather.py
```

演示内容包括：
1. 按位置查询气象
2. 按时间查询气象
3. 自动选择观测点
4. 对比多个位置
5. 访问结构化数据
6. 错误处理

## 测试

运行测试套件：

```bash
pytest tests/tools/test_get_weather.py -v
```

测试覆盖：
- ✅ 工具元数据验证
- ✅ 参数校验
- ✅ 位置查询
- ✅ 时间查询
- ✅ 自动位置选择
- ✅ 错误处理
- ✅ 数据格式化
- ✅ 最近邻匹配算法

## 集成到Agent系统

工具已注册到 `tools/registry.py`：

```python
ToolRegistry.register(GetWeatherTool(), ["common"])
```

这意味着该工具在所有场景（oil_spill, bird_strike等）中都可用。

### Agent调用示例

在应急响应场景中，Agent可能会：

```
User: 501机位发生燃油泄漏，请帮我评估风险

Agent: [调用get_weather获取当前气象条件]
【05L 气象信息】
观测时间: 23:59:58
🌬️  风: 278° 2.3 m/s (轻风)

[调用assess_risk进行风险评估]
根据当前气象条件（轻风2.3m/s），燃油蒸汽扩散速度较慢...
```

## 配置选项

### 修改时间匹配窗口

默认为1小时，可在 `find_nearest_record()` 中修改：

```python
# 当前：3600秒（1小时）
if nearest['time_diff'].total_seconds() > 3600:
    return None

# 修改为30分钟
if nearest['time_diff'].total_seconds() > 1800:
    return None
```

### 添加新的位置映射

在 `GetWeatherTool.execute()` 中修改：

```python
position_to_sensor = {
    "501": "05L",
    "601": "06L",
    "701": "07L",  # 添加新映射
    # ...
}
```

### 自定义输出格式

修改 `format_weather_info()` 函数以自定义显示格式。

## 性能考虑

- **数据缓存**: 气象数据在首次加载后缓存在内存中
- **懒加载**: 只在首次调用时加载数据
- **索引优化**: 使用pandas的索引加速查询

### 预期性能

- 加载数据：~1秒（5154条记录）
- 单次查询：<100ms
- 内存占用：~2MB

## 故障排查

### 问题：未找到气象数据

**症状**：
```
❌ 气象数据不可用
```

**解决方案**：
```bash
python scripts/data_processing/extract_awos_weather.py
```

### 问题：位置不存在

**症状**：
```
❌ 未找到位置 'XXX' 的气象数据
```

**解决方案**：
- 检查位置ID拼写
- 运行 `analyze_awos_weather.py` 查看可用位置
- 使用 `location="推荐"` 自动选择

### 问题：时间差过大

**症状**：
返回None，即使有该位置的数据

**原因**：查询时间与数据时间相差超过1小时

**解决方案**：
- 检查时间戳格式
- 使用数据中的时间范围
- 调整时间匹配窗口

## 扩展开发

### 添加新的气象字段

1. 在 `extract_awos_weather.py` 中提取新字段
2. 在 `GetWeatherTool` 中添加字段到返回值
3. 更新 `format_weather_info()` 显示新字段

### 添加气象预警功能

```python
def check_weather_alerts(weather: dict) -> List[str]:
    """检查气象预警条件"""
    alerts = []

    if weather.get('wind_speed', 0) > 10:
        alerts.append("⚠️ 强风警告")

    if weather.get('visibility', 99999) < 1000:
        alerts.append("⚠️ 低能见度警告")

    if weather.get('temperature', 0) < -10:
        alerts.append("⚠️ 低温警告")

    return alerts
```

### 集成到风险评估

修改风险评估工具，将气象条件纳入评分：

```python
# 在 assess_risk.py 中
weather_info = state.get('weather', {})
wind_speed = weather_info.get('wind_speed', 0)

if wind_speed > 5:
    risk_score += 10  # 强风增加风险
```

## 相关文档

- [AWOS数据处理](./AWOS_WEATHER_PROCESSING.md)
- [工具开发指南](../CLAUDE.md#tool-development-guide)
- [API文档](./API_DOCUMENTATION.md)

## 更新日志

### 2026-01-13
- ✅ 创建 get_weather 工具
- ✅ 集成到工具注册中心
- ✅ 添加完整测试覆盖
- ✅ 创建演示脚本
- ✅ 编写使用文档

## 贡献者

- Claude Code (AI Assistant)

## 许可证

本项目采用 MIT 许可证。
