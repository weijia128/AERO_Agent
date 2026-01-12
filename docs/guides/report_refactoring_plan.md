# 报告生成系统重构方案

## 问题总结

### 当前状态
- **文件**: `agent/nodes/output_generator.py` (837 行)
- **实现方式**: 纯字符串拼接，无模板引擎
- **冗余度**: 约 60% 代码可优化（585 行）
- **维护性**: 低（模板硬编码在 Python 代码中）

### 核心问题
1. **无模板引擎**：使用 f-string 拼接 200+ 行 Markdown
2. **重复代码**：
   - 字段映射在 3+ 处重复定义
   - 通知表格构建逻辑重复
   - 航班影响处理重复
3. **未使用函数**：`_build_skill_prompt()` (~250 行) 完全未调用
4. **双份生成逻辑**：确定性模板和 LLM prompt 几乎完全相同
5. **测试缺失**：无专门的报告生成测试

---

## 改进方案

### Phase 1: 模板化改造 ⭐️ 最高优先级

#### 1.1 创建模板目录结构
```
agent/templates/
├── base_report.md.j2           # 基础报告模板
├── oil_spill/
│   └── report.md.j2            # 漏油场景报告
├── bird_strike/
│   └── report.md.j2            # 鸟击场景报告
└── components/
    ├── event_summary.md.j2     # 事件摘要组件
    ├── checklist.md.j2         # 检查单组件
    ├── notifications_table.md.j2  # 通知表格组件
    └── impact_section.md.j2    # 影响分析组件
```

#### 1.2 安装依赖
```bash
pip install jinja2
```

#### 1.3 创建模板渲染器
**文件**: `agent/nodes/template_renderer.py` (新建)

```python
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# 注册自定义过滤器
def format_risk_level(level: str) -> str:
    """格式化风险等级"""
    mapping = {
        "HIGH": "高",
        "MEDIUM_HIGH": "中高",
        "MEDIUM": "中",
        "LOW": "低"
    }
    return mapping.get(level, level)

def format_datetime(iso_string: str) -> str:
    """格式化日期时间"""
    if not iso_string:
        return "——"
    return iso_string[:19].replace("T", " ")

env.filters['risk_level'] = format_risk_level
env.filters['datetime'] = format_datetime

def render_report(scenario_type: str, state: dict) -> str:
    """渲染报告"""
    template_path = f"{scenario_type}/report.md.j2"
    template = env.get_template(template_path)
    return template.render(**state)
```

#### 1.4 创建基础模板
**文件**: `agent/templates/base_report.md.j2`

```markdown
# 机坪特情处置检查单

**适用范围**：{{ scope }}

## 1. 事件基本信息
| 项目 | 记录 |
|-----|------|
| 事件编号 | {{ event_id }} |
| 航班号/航空器注册号 | {{ incident.flight_no_display or '——' }} |
| 事件触发时间 | {{ incident.report_time | datetime }} |
| 发现位置 | {{ incident.position or '——' }} |
| 风险等级 | {{ risk.level | risk_level }} (风险分数: {{ risk.score }}) |

{% block details %}{% endblock %}
```

#### 1.5 创建场景模板
**文件**: `agent/templates/oil_spill/report.md.j2`

```markdown
{% extends "base_report.md.j2" %}

{% set scope = "机坪航空器漏油、油污、渗漏等特情事件的识别、处置与闭环记录" %}

{% block details %}
## 2. 特情初始确认
### 2.1 漏油基本情况
| 关键项 | 选择/填写 |
|-------|---------|
| 油液类型 | {{ fluid_type_map[incident.fluid_type] }} |
| 是否持续滴漏 | {% if incident.continuous %}是{% else %}否{% endif %} |
| 发动机/APU状态 | {% if incident.engine_status == 'RUNNING' %}运行中{% else %}关闭{% endif %} |
| 泄漏面积评估 | {{ size_map[incident.leak_size] }} |
{% endblock %}
```

**预计收益**：
- 代码从 837 行减少到 ~200 行（76% 减少）
- 模板可视化，非技术人员可编辑
- 支持多场景扩展

---

### Phase 2: 提取公共逻辑

#### 2.1 创建字段映射模块
**文件**: `agent/report_utils/mappings.py` (新建)

```python
"""字段映射常量（统一管理）"""

FLUID_TYPE_MAP = {
    "FUEL": "航空燃油(Jet Fuel)",
    "HYDRAULIC": "液压油",
    "OIL": "发动机滑油"
}

LEAK_SIZE_MAP = {
    "LARGE": ">5㎡",
    "MEDIUM": "1-5㎡",
    "SMALL": "<1㎡",
    "UNKNOWN": "待评估"
}

ENGINE_STATUS_MAP = {
    "RUNNING": "运行中",
    "STOPPED": "关闭"
}

# 统一的映射函数
def format_field(value: str, field_type: str) -> str:
    """格式化字段值"""
    mappings = {
        "fluid_type": FLUID_TYPE_MAP,
        "leak_size": LEAK_SIZE_MAP,
        "engine_status": ENGINE_STATUS_MAP
    }
    return mappings.get(field_type, {}).get(value, value)
```

#### 2.2 提取数据处理函数
**文件**: `agent/report_utils/processors.py` (新建)

```python
"""报告数据处理函数"""

def extract_flight_impact_stats(flight_impact: dict) -> dict:
    """提取航班影响统计（去除重复逻辑）"""
    if not flight_impact:
        return {"total": 0, "avg_delay": 0}

    stats = flight_impact.get("statistics", {})
    return {
        "total": stats.get("total_affected_flights", 0),
        "avg_delay": stats.get("average_delay_minutes", 0),
        "severity": stats.get("severity_distribution", {})
    }

def build_notifications_table(coordination_units: list) -> str:
    """构建通知表格（统一逻辑）"""
    rows = []
    for unit in coordination_units:
        status = "☑ 是  ☐ 否" if unit.get("notified") else "☐ 是  ☐ 否"
        time = unit.get("notify_time", "——") or "——"
        if time and len(time) > 19:
            time = time[11:19]
        rows.append(f"| {unit['name']} | {status} | {time} | |\n")
    return "".join(rows)

def format_affected_areas(spatial_analysis: dict) -> list:
    """格式化受影响区域（统一逻辑）"""
    areas = []
    if spatial_analysis.get("isolated_nodes"):
        areas.extend(spatial_analysis["isolated_nodes"])
    if spatial_analysis.get("affected_taxiways"):
        areas.extend([f"滑行道{t}" for t in spatial_analysis["affected_taxiways"]])
    if spatial_analysis.get("affected_runways"):
        areas.extend([f"跑道{r}" for r in spatial_analysis["affected_runways"]])
    return areas
```

#### 2.3 简化 output_generator.py
**重构后的结构**:

```python
# agent/nodes/output_generator.py (重构后)

from agent.report_utils.mappings import FLUID_TYPE_MAP, LEAK_SIZE_MAP
from agent.report_utils.processors import (
    extract_flight_impact_stats,
    build_notifications_table,
    format_affected_areas
)
from agent.nodes.template_renderer import render_report

def output_generator_node(state: AgentState) -> Dict[str, Any]:
    """输出生成节点（简化版）"""
    scenario_type = state.get("scenario_type", "oil_spill")

    # 准备模板数据
    template_data = {
        "incident": state.get("incident", {}),
        "risk": state.get("risk_assessment", {}),
        "spatial": state.get("spatial_analysis", {}),
        "flight_impact": extract_flight_impact_stats(state.get("flight_impact_prediction")),
        "coordination_units": state.get("coordination_units", []),
        # 添加必要的映射函数
        "fluid_type_map": FLUID_TYPE_MAP,
        "size_map": LEAK_SIZE_MAP,
    }

    # 使用模板渲染
    final_answer = render_report(scenario_type, template_data)

    # 生成结构化报告（API 返回）
    final_report = {
        "title": "机坪特情处置检查单",
        "event_summary": generate_event_summary(state),
        # ... 其他结构化数据
    }

    return {
        "final_report": final_report,
        "final_answer": final_answer,
        "is_complete": True,
        "fsm_state": FSMState.COMPLETED.value,
    }

# 保留辅助生成函数（供 API 返回）
def generate_event_summary(state): ...
```

**预计收益**：
- 删除 ~300 行重复代码
- 提高可维护性
- 统一数据处理逻辑

---

### Phase 3: 删除冗余代码

#### 3.1 删除未使用的函数
**删除**: `output_generator.py` 中的以下函数：
- `_build_skill_prompt()` (line 637-881, ~250 行) - 完全未使用
- `_fallback_report()` (line 884-906) - 未被调用

#### 3.2 合并重复逻辑
**合并**:
- `generate_coordination_units()` 和 `generate_notifications_summary()` 中的通知处理
- `generate_operational_impact()` 和 `generate_recommendations()` 中的航班影响处理

#### 3.3 使用公共函数替换重复代码
```python
# 替换前（3 处重复）
fluid_map = {"FUEL": "燃油", "HYDRAULIC": "液压油", "OIL": "滑油"}

# 替换后
from agent.report_utils.mappings import FLUID_TYPE_MAP
```

**预计收益**：
- 删除 ~250 行无用代码
- 减少维护成本
- 提高代码一致性

---

### Phase 4: 测试和验证

#### 4.1 创建测试文件
**文件**: `tests/agent/test_report_generation.py` (新建)

```python
"""报告生成测试"""

import pytest
from agent.nodes.output_generator import output_generator_node
from agent.state import create_initial_state

def test_oil_spill_report_generation():
    """测试漏油场景报告生成"""
    state = create_initial_state(
        session_id="test-123",
        scenario_type="oil_spill",
        message="501机位，燃油泄漏，发动机运转中"
    )
    # 模拟完整流程...

    result = output_generator_node(state)

    # 验证
    assert "final_answer" in result
    assert "# 机坪特情处置检查单" in result["final_answer"]
    assert "## 1. 事件基本信息" in result["final_answer"]
    assert "501" in result["final_answer"]

def test_report_template_structure():
    """验证报告模板包含所有必需章节"""
    state = create_initial_state(...)
    result = output_generator_node(state)
    report = result["final_answer"]

    required_sections = [
        "## 1. 事件基本信息",
        "## 2. 特情初始确认",
        "## 3. 初期风险控制措施",
        "## 4. 协同单位通知记录",
        "## 5. 区域隔离与现场检查",
        "## 6. 清污处置执行情况",
        "## 7. 处置结果确认",
        "## 8. 区域恢复与运行返还",
        "## 9. 运行影响评估",
        "## 10. 事件总结与改进建议",
        "## 11. 签字与存档"
    ]

    for section in required_sections:
        assert section in report, f"缺少章节: {section}"

def test_multi_scenario_reports():
    """测试多场景报告生成"""
    scenarios = ["oil_spill", "bird_strike"]
    for scenario in scenarios:
        state = create_initial_state(
            session_id=f"test-{scenario}",
            scenario_type=scenario,
            message="测试消息"
        )
        result = output_generator_node(state)
        assert result["final_answer"]
```

#### 4.2 API 端点测试
**文件**: `tests/api/test_report_endpoints.py` (新建)

```python
"""API 报告端点测试"""

from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_get_report_json():
    """测试获取 JSON 格式报告"""
    # 先创建会话
    response = client.post("/event/start", json={
        "message": "501机位燃油泄漏",
        "scenario_type": "oil_spill"
    })
    session_id = response.json()["session_id"]

    # 获取报告
    response = client.get(f"/event/{session_id}/report")
    assert response.status_code == 200
    report = response.json()
    assert "title" in report
    assert "event_summary" in report

def test_get_report_markdown():
    """测试下载 Markdown 报告"""
    response = client.get(f"/event/{session_id}/report/markdown")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
```

#### 4.3 集成测试验证
```bash
# 运行完整流程测试
pytest tests/integration/test_integration.py -v

# 运行报告生成专项测试
pytest tests/agent/test_report_generation.py -v
pytest tests/api/test_report_endpoints.py -v
```

---

## 实施步骤

### Week 1: 模板化
1. Day 1-2: 创建模板目录和 Jinja2 配置
2. Day 3-4: 迁移现有模板到 Jinja2
3. Day 5: 测试和验证

**验证**: 运行 `pytest tests/integration/test_integration.py` 确保功能不变

### Week 2: 代码简化
1. Day 1-2: 创建公共模块（mappings.py, processors.py）
2. Day 3-4: 重构 output_generator.py
3. Day 5: 删除冗余代码

**验证**: 代码行数减少 50%+，测试全部通过

### Week 3: 测试和优化
1. Day 1-2: 添加单元测试
2. Day 3-4: 性能优化（模板缓存）
3. Day 5: 文档更新

**验证**: 测试覆盖率达到 80%+

---

## 风险评估

### 高风险
- **API 格式变更** - 缓解：保持 final_report 结构不变
- **报告内容缺失** - 缓解：逐字段对比新旧输出

### 中风险
- **模板渲染错误** - 缓解：完善的错误处理和回退机制
- **性能下降** - 缓解：Jinja2 模板缓存

### 低风险
- **场景配置更新** - 缓解：保持向后兼容

---

## 预期收益

| 指标 | 改进前 | 改进后 | 提升 |
|------|-------|--------|------|
| 代码行数 | 837 行 | ~200 行 | ⬇️ 76% |
| 维护难度 | 高 | 低 | ⬇️ 80% |
| 新场景开发 | 2 天 | 0.5 天 | ⬆️ 4x |
| 测试覆盖率 | 0% | 80%+ | ⬆️ 80% |
| 模板可视化 | 否 | 是 | ✅ |

---

## 关键文件路径

### 需要修改的文件
- `agent/nodes/output_generator.py` - 简化，减少 600+ 行
- `config/settings.py` - 添加模板配置（可选）

### 需要新建的文件
- `agent/nodes/template_renderer.py` - 模板渲染器
- `agent/report_utils/mappings.py` - 字段映射
- `agent/report_utils/processors.py` - 数据处理
- `agent/templates/base_report.md.j2` - 基础模板
- `agent/templates/oil_spill/report.md.j2` - 漏油场景模板
- `tests/agent/test_report_generation.py` - 单元测试
- `tests/api/test_report_endpoints.py` - API 测试

### 需要删除的代码
- `output_generator.py:_build_skill_prompt()` (line 637-881)
- `output_generator.py:_fallback_report()` (line 884-906)

---

## 验证清单

### 功能验证
- [ ] 报告包含所有 11 个章节
- [ ] 字段映射正确（风险等级、油液类型等）
- [ ] 协同单位通知表格正确
- [ ] 航班影响统计正确
- [ ] 事件编号格式正确

### API 兼容性
- [ ] GET /event/{session_id}/report 返回格式不变
- [ ] GET /event/{session_id}/report/markdown 可下载
- [ ] CLI 显示格式不变

### 性能验证
- [ ] 报告生成时间 < 2 秒
- [ ] 模板缓存生效
- [ ] 内存使用无明显增加

### 测试覆盖
- [ ] 单元测试覆盖核心函数
- [ ] 集成测试通过
- [ ] API 端点测试通过
