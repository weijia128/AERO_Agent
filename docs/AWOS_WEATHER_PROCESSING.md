# AWOS气象数据处理工具

## 概述

本项目提供了一套完整的AWOS（机场气象观测系统）日志数据处理工具，可以提取、清洗、分析和导出气象数据。

## 数据结构

AWOS日志包含多种消息类型：

### 消息类型

| 消息类型 | 说明 | 主要字段 |
|---------|------|---------|
| **WIND** | 风数据 | wdins（风向）、wsins（风速）、wd10m/ws10m（10米）、wd2m/ws2m（2米）、cw2a（横风）、hw2a（顶风） |
| **HUMITEMP** | 温湿度数据 | tains（温度）、tdins（露点）、rhins（相对湿度） |
| **PRESS** | 气压数据 | qnhins（QNH）、qfeins（QFE）、pains（站压） |
| **VIS** | 能见度数据 | vis（能见度）、rvr（RVR） |
| **RAIN** | 降雨数据 | amount_ins、sum_ins、sum_1h |
| **CLOUD** | 云数据 | cloudbase、amount1-4 |
| **PW** | 现在天气数据 | prss、wxnws |

### 位置标识

- **跑道端**: 05L, 05R, 06L, 06R, 23L, 23R, 24L, 24R
- **区域**: NORTH, SOUTH, ACTIVE

## 工具脚本

### 1. extract_awos_weather.py

**功能**: 从AWOS日志文件中提取气象数据并清洗

**使用方法**:
```bash
python scripts/data_processing/extract_awos_weather.py
```

**输入**: `data/raw/气象数据/AWOS_*.log`

**输出**: `data/processed/awos_weather_<timestamp>.csv`

**提取的字段**:
- 风向/风速（多层高度）
- 温度/露点/相对湿度
- QNH/QFE/站压
- 能见度/RVR

**数据清洗规则**:
- `"///"` → `None`（缺失值）
- `null` → `None`
- 保留 `0.0`（可能是有效值）

**示例输出**:
```
📂 找到 24 个AWOS日志文件
⏳ 处理: AWOS_2026-01-06_05h.log
   ✅ 提取了 246 条记录
...
✅ 数据已保存到: awos_weather_20260113_135013.csv
   总计 5154 条合并后的记录
   涵盖 8 个位置
```

### 2. analyze_awos_weather.py

**功能**: 对提取的气象数据进行统计分析

**使用方法**:
```bash
python scripts/data_processing/analyze_awos_weather.py
```

**输入**: 最新的 `awos_weather_*.csv`

**输出**:
1. `data/processed/awos_analysis_report_<timestamp>.txt` - 文本分析报告
2. `data/processed/awos_per_location/` - 按位置分离的CSV文件

**分析内容**:
- 总体字段统计（有效记录数、范围、平均值、标准差）
- 按位置详细统计
- 数据质量检测（异常值、无效值）

**示例输出**:
```
📊 AWOS气象数据分析工具
📂 加载数据: awos_weather_20260113_135013.csv
   ✅ 总计 5154 条记录
   ✅ 8 个位置

📁 按位置分离数据...
   ✅ 05L: 831 条记录 -> awos_05L.csv
   ✅ 06L: 795 条记录 -> awos_06L.csv
   ...
```

### 3. export_awos_to_excel.py

**功能**: 数据清洗和Excel导出

**使用方法**:
```bash
python scripts/data_processing/export_awos_to_excel.py
```

**输入**: 最新的 `awos_weather_*.csv`

**输出**: `data/processed/awos_weather_<timestamp>.xlsx`

**数据清洗选项**:
1. **不清洗**: 使用原始数据
2. **删除缺失值** (`drop`): 删除包含缺失值的行
3. **前向填充** (`ffill`): 用前一个有效值填充
4. **线性插值** (`interpolate`): 线性插值填充（推荐）

**Excel工作表**:
1. **原始数据**: 原始提取的数据
2. **清洗后数据**: 经过清洗处理的数据
3. **位置统计**: 每个位置的统计摘要
4. **数据质量**: 每个字段的完整率统计
5. **小时平均值**: 按小时聚合的平均值（用于趋势分析）

**示例输出**:
```
🧹 AWOS气象数据清洗和导出工具
⏳ 正在清洗数据... (方法: interpolate)
   ✅ 清洗完成
   填充缺失值: 46146 个
   剩余缺失值: 9745 个

💾 导出到Excel...
   ✅ 已保存: awos_weather_20260113_135444.xlsx
```

## 完整工作流程

### 标准流程

```bash
# 步骤1: 提取数据
python scripts/data_processing/extract_awos_weather.py

# 步骤2: 分析数据
python scripts/data_processing/analyze_awos_weather.py

# 步骤3: 导出Excel（可选）
python scripts/data_processing/export_awos_to_excel.py
```

### 输出文件说明

运行完成后，`data/processed/` 目录将包含：

```
data/processed/
├── awos_weather_20260113_135013.csv                    # 原始合并数据
├── awos_analysis_report_20260113_135135.txt            # 分析报告
├── awos_weather_20260113_135444.xlsx                   # Excel导出（含清洗）
└── awos_per_location/                                  # 按位置分离的数据
    ├── awos_05L.csv
    ├── awos_06L.csv
    ├── awos_06R.csv
    ├── awos_23R.csv
    ├── awos_24L.csv
    ├── awos_24R.csv
    ├── awos_NORTH.csv
    └── awos_SOUTH.csv
```

## 数据使用示例

### Python中使用提取的CSV

```python
import pandas as pd

# 加载数据
df = pd.read_csv('data/processed/awos_weather_20260113_135013.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# 查看特定位置的数据
df_05L = df[df['location_id'] == '05L']

# 计算小时平均值
df['hour'] = df['timestamp'].dt.floor('h')
hourly_avg = df.groupby(['hour', 'location_id']).agg({
    'temperature': 'mean',
    'wind_speed': 'mean',
    'wind_direction': 'mean',
}).reset_index()

# 筛选特定时间段
from datetime import datetime
mask = (df['timestamp'] >= datetime(2026, 1, 6, 5, 0)) & \
       (df['timestamp'] <= datetime(2026, 1, 6, 6, 0))
df_period = df[mask]
```

### 在Agent中使用

```python
# 在tools/information/目录下创建新工具 get_weather.py
from tools.base import BaseTool

class GetWeatherTool(BaseTool):
    """
    从AWOS数据中获取特定时间和位置的气象信息
    """
    name = "get_weather"
    description = "获取特定时间和位置的气象数据（温度、风速、气压等）"

    def execute(self, state, inputs):
        location = inputs.get('location')
        timestamp = inputs.get('timestamp')

        # 读取AWOS数据
        df = pd.read_csv('data/processed/awos_weather_latest.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 筛选数据
        match = df[(df['location_id'] == location) &
                   (df['timestamp'] == timestamp)]

        if len(match) == 0:
            return {
                'observation': f"未找到位置 {location} 在 {timestamp} 的气象数据",
                'success': False
            }

        row = match.iloc[0]
        result = {
            'temperature': row['temperature'],
            'wind_speed': row['wind_speed'],
            'wind_direction': row['wind_direction'],
            'qnh': row['qnh'],
            'relative_humidity': row['relative_humidity'],
        }

        return {
            'observation': f"气象数据: {result}",
            'success': True,
            'state_updates': {'weather': result}
        }
```

## 数据质量说明

### 字段完整性

基于2026-01-06的数据：

| 字段类别 | 字段 | 完整率 |
|---------|------|--------|
| 风 | wind_direction, wind_speed | ~40% |
| 温湿度 | temperature, dew_point, rh | ~28% |
| 能见度 | visibility, rvr | ~28% |
| 气压 | qnh, qfe, station_pressure | ~19% |

### 缺失原因

1. **传感器位置不同**: 不同位置安装的传感器类型不同
   - 跑道端: 有能见度/RVR传感器
   - 气象观测点: 有温湿度和气压传感器
   - 风传感器: 部分位置有

2. **采样频率不同**: 不同传感器的采样频率可能不一致

3. **数据传输问题**: 部分数据可能在传输中丢失

### 数据清洗建议

- **默认使用线性插值**: 对于连续变量（温度、气压），插值效果较好
- **风数据慎用插值**: 风向/风速变化快，插值可能不准确，建议使用前向填充或保留缺失
- **按位置分析**: 不同位置的数据完整性差异大，建议分开分析

## 扩展开发

### 添加新的消息类型

编辑 `extract_awos_weather.py`:

```python
def extract_rain_data(data: Dict) -> Dict[str, Any]:
    """提取RAIN类型的数据"""
    return {
        'rain_amount': clean_value(data.get('amount_ins')),
        'rain_sum_1h': clean_value(data.get('sum_1h')),
        'rain_duration_1h': clean_value(data.get('duaration_1h')),
    }

# 在process_awos_file中添加:
elif message_type == 'RAIN':
    record.update(extract_rain_data(data))
```

### 添加可视化

可以使用matplotlib或plotly创建可视化：

```python
import matplotlib.pyplot as plt

# 温度趋势图
df_hourly = df.groupby('hour')['temperature'].mean()
plt.figure(figsize=(12, 6))
df_hourly.plot()
plt.title('24小时温度变化趋势')
plt.xlabel('时间')
plt.ylabel('温度 (°C)')
plt.savefig('temperature_trend.png')
```

## 常见问题

**Q: 为什么某些位置的数据很少？**

A: 不同的传感器安装在不同的位置。例如：
- 05L, 06L: 跑道端，有能见度/RVR传感器
- NORTH, SOUTH: 区域气象站，可能有风传感器
- 具体配置取决于机场设备布局

**Q: 如何处理缺失值？**

A: 根据使用场景选择：
- **统计分析**: 可以删除缺失值（`drop`）
- **时间序列分析**: 使用插值（`interpolate`）或前向填充（`ffill`）
- **实时应用**: 保留缺失值，标记为无效

**Q: 数据精度如何？**

A: 数据来自AWOS系统，精度取决于传感器：
- 温度: 通常±0.5°C
- 风速: 通常±0.5 m/s
- 气压: 通常±0.1 hPa
- 能见度: 通常±10%

## 参考资料

- [AWOS系统说明](https://en.wikipedia.org/wiki/Automated_airport_weather_station)
- [METAR格式](https://en.wikipedia.org/wiki/METAR)
- 项目主文档: [CLAUDE.md](../../CLAUDE.md)
