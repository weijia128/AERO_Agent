# 机场拓扑图集成完成总结

## 概述

成功将基于真实轨迹数据聚类生成的机场拓扑图集成到应急响应系统中，实现了基于历史数据的航班影响预测功能。

## 完成的工作

### 1. 拓扑图数据准备（scripts/data_processing/）

#### 已完成的数据处理工具：

- **trajectory_clustering.py** - 轨迹聚类分析器（正确方法）
  - 基于停留时间识别机位（低速停留 ≥30秒）
  - 基于速度模式识别跑道（速度 ≥30 m/s）
  - 基于轨迹密度识别滑行道（2-20 m/s速度范围）
  - 避免依赖可能误导的字段语义（如trajectory数据中的runway字段）

- **build_topology_from_clustering.py** - 拓扑图构建器
  - 从聚类结果构建节点（机位、跑道、滑行道）
  - 基于实际滑行轨迹构建边（连接关系）
  - 合并距离很近的同类节点（50米阈值）
  - 过滤异常节点（10公里半径过滤）

- **visualize_clustering_topology.py** - 可视化工具
  - 生成交互式HTML可视化（使用Plotly）
  - 按类型区分节点颜色
  - 边的粗细表示使用频率

#### 生成的拓扑图数据：

**文件**: `scripts/data_processing/topology_clustering_based.json`

**统计信息**:
- 总节点数: 124
  - 机位: 68
  - 跑道: 3
  - 滑行道: 53
- 总边数: 153
- 覆盖范围: 4.3km × 2.6km（合理的机场尺寸）
- 跑道间距: 约3km（符合实际）

### 2. 拓扑加载器（tools/spatial/topology_loader.py）

创建了全局拓扑加载器，提供以下功能：

```python
from tools.spatial.topology_loader import get_topology_loader

# 获取拓扑加载器实例（单例模式）
topology = get_topology_loader()

# 核心API
topology.get_node(node_id)                    # 获取节点信息
topology.get_adjacent_nodes(node_id)          # 获取邻接节点
topology.get_nodes_by_type(node_type)         # 按类型获取节点
topology.find_nearest_node(position_str)      # 查找最近节点
topology.get_stand_info(stand_id)             # 获取机位详细信息
topology.bfs_spread(start_node, max_hops)     # BFS扩散算法
topology.get_statistics()                     # 获取统计信息
```

**特性**:
- 自动加载拓扑图JSON文件
- 构建邻接表（无向图）
- 节点类型索引
- BFS图搜索算法
- 位置模糊匹配

### 3. 更新现有空间工具

#### tools/spatial/get_stand_location.py

- ✅ 替换MOCK_TOPOLOGY为真实拓扑数据
- ✅ 返回真实的坐标、相邻滑行道信息
- ✅ 支持位置模糊匹配

**示例输出**:
```
停机位 stand_0 信息（基于真实拓扑）:
坐标=(34.45168, 108.77354),
相邻滑行道=['taxiway_26'],
最近跑道=runway_1,
观测次数=1,
平均停留时间=223秒
```

#### tools/spatial/calculate_impact_zone.py

- ✅ 替换MOCK_TOPOLOGY为真实拓扑数据
- ✅ 使用真实拓扑的BFS扩散算法
- ✅ 基于实际节点连接关系计算影响范围

**示例输出**:
```
影响范围分析完成（基于真实拓扑）:
起始节点=stand_0,
隔离区域=9个节点,
受影响机位=6个,
受影响滑行道=3个,
受影响跑道=0个
```

### 4. 新增航班影响预测工具

#### tools/spatial/predict_flight_impact.py

**功能**:
- 加载历史航班计划数据
- 筛选时间窗口内的航班
- 匹配受影响的航班（基于机位、跑道、滑行道）
- 计算延误时间（基于延误规则）
- 生成影响统计报告

**延误估算规则**:
| 影响类型 | 出港延误 | 进港延误 |
|---------|---------|---------|
| 机位封锁 | 30分钟 | 45分钟 |
| 滑行道封锁 | 15分钟 | 20分钟 |
| 跑道封锁 | 60分钟 | 60分钟 |

**使用方式**:
```python
from tools.spatial.predict_flight_impact import PredictFlightImpactTool

tool = PredictFlightImpactTool()

# state需要包含spatial_analysis（来自calculate_impact_zone）
result = tool.execute(state, {
    "time_window": 2,  # 预测2小时窗口
    "use_cache": True
})

# 返回结果包含：
# - affected_flights: 受影响航班列表
# - statistics: 统计信息
# - time_window: 时间窗口信息
```

**示例输出**:
```
航班影响预测完成（基于历史数据）:
时间窗口: 11:00 - 13:00 (2小时)
受影响航班总数: 15 架次
累计延误时间: 450 分钟
平均延误: 30.0 分钟/架次
影响分布: 严重 3 架次, 中等 8 架次, 轻微 4 架次

受影响最严重的航班（前5）:
1. CES5201: 延误 60 分钟 (跑道封锁, 机位=stand_12, 跑道=runway_1)
2. CSN6789: 延误 45 分钟 (机位封锁, 机位=stand_10, 跑道=05L)
...
```

### 5. 工具注册

在 `tools/registry.py` 中注册新工具：

```python
ToolRegistry.register(PredictFlightImpactTool(), ["oil_spill"])
```

### 6. 集成测试

创建了完整的测试套件 `test_topology_integration.py`：

**测试覆盖**:
1. ✅ 拓扑加载器测试
2. ✅ 机位位置查询工具测试
3. ✅ 影响范围计算工具测试
4. ✅ 航班影响预测工具测试
5. ✅ 端到端场景测试

**测试结果**: 5/5 通过 ✓

## 数据流程

```
用户输入事件信息
    ↓
[1] get_stand_location
    - 查询事发位置详细信息
    - 使用真实拓扑图数据
    ↓
[2] assess_risk
    - 评估风险等级（HIGH/MEDIUM/LOW）
    ↓
[3] calculate_impact_zone
    - BFS扩散算法计算影响范围
    - 基于真实拓扑图连接关系
    - 输出受影响的机位/跑道/滑行道列表
    ↓
[4] predict_flight_impact
    - 加载历史航班计划数据
    - 匹配受影响航班
    - 计算延误时间
    - 生成影响报告
    ↓
输出完整应急响应报告
```

## 技术架构改进

### 从模拟数据到真实数据

**之前**:
```python
# 硬编码的模拟拓扑
MOCK_TOPOLOGY = {
    "stands": {
        "501": {"adjacent": ["502", "A", "A3"]},
        ...
    }
}
```

**现在**:
```python
# 基于真实轨迹数据的拓扑
topology = get_topology_loader()  # 加载真实拓扑图
node = topology.get_node(node_id)  # 获取真实节点数据
```

### 聚类方法的重要性

**错误方法**（之前尝试过）:
- 直接使用轨迹数据中的 `runway` 字段识别跑道位置
- 问题：该字段表示"计划使用的跑道"，而非当前位置
- 结果：跑道位置出现在滑行道/机位上（明显错误）

**正确方法**（当前实现）:
- 基于物理特征的聚类：
  - 停留时间 → 机位
  - 速度模式 → 跑道
  - 轨迹密度 → 滑行道
- 结果：跑道间距3km（合理），机场尺寸4.3km × 2.6km（合理）

## 使用指南

### 1. 运行测试

```bash
cd /path/to/airport-emergency-agent
python test_topology_integration.py
```

### 2. 在Agent中使用

工具已自动注册到 `oil_spill` 场景，Agent可以自动调用：

```python
# Agent会自动按顺序调用这些工具：
# 1. get_stand_location - 查询位置
# 2. assess_risk - 评估风险
# 3. calculate_impact_zone - 计算影响范围
# 4. predict_flight_impact - 预测航班影响
# 5. generate_report - 生成报告
```

### 3. 独立使用工具

```python
from tools.spatial.topology_loader import get_topology_loader
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool
from tools.spatial.predict_flight_impact import PredictFlightImpactTool

# 1. 准备状态
state = {
    "incident": {
        "position": "stand_5",
        "fluid_type": "FUEL"
    },
    "risk_assessment": {
        "level": "HIGH"
    }
}

# 2. 计算影响范围
impact_tool = CalculateImpactZoneTool()
impact_result = impact_tool.execute(state, {})
state["spatial_analysis"] = impact_result["spatial_analysis"]

# 3. 预测航班影响
predict_tool = PredictFlightImpactTool()
predict_result = predict_tool.execute(state, {"time_window": 2})

print(predict_result["observation"])
```

## 数据文件位置

### 输入数据
- 轨迹数据: `data/raw/航迹数据/*.log`
- 航班计划: `data/raw/航班计划/Log_*.txt`

### 输出数据
- 拓扑图: `scripts/data_processing/topology_clustering_based.json`
- 可视化: `scripts/data_processing/topology_visualization_correct.html`

### 预处理脚本
- `scripts/data_processing/trajectory_clustering.py` - 生成聚类结果
- `scripts/data_processing/build_topology_from_clustering.py` - 生成拓扑图
- `scripts/data_processing/visualize_clustering_topology.py` - 生成可视化

## 性能优化

1. **拓扑加载器单例模式**: 避免重复加载JSON文件
2. **航班数据缓存**: `predict_flight_impact` 工具缓存已加载的航班数据
3. **邻接表预构建**: 拓扑加载时就构建邻接表，加速BFS搜索

## 后续可能的改进

1. **动态时间窗口**: 根据事件严重程度自动调整预测时间窗口
2. **更精细的延误模型**: 考虑天气、时段等因素
3. **可视化集成**: 在应急响应界面中展示受影响区域
4. **多场景支持**: 将拓扑图应用到其他场景（鸟击、跑道入侵等）
5. **实时数据对接**: 对接实时航班数据系统

## 总结

✅ 成功将基于真实轨迹数据的机场拓扑图集成到应急响应系统
✅ 实现了基于历史数据的航班影响预测
✅ 所有工具测试通过
✅ 数据驱动的方法替代了硬编码的模拟数据
✅ 为系统提供了可靠的空间分析和影响评估能力

系统现已具备完整的预测性评估能力，可以根据事发位置和风险等级，预测对航班运行的影响。
