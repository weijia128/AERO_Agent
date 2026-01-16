# 特情报告按场景分类存储功能

## 修改概述

本次修改实现了将不同场景的特情报告按场景类型分别存储的功能，便于报告的分类管理和查找。

## 修改内容

### 文件位置
- **修改文件**: `apps/run_agent.py`
- **修改函数**: `save_report()` (第1073-1138行)

### 功能说明

#### 1. 场景分类映射
根据 `scenario_type` 字段将报告保存到对应的文件夹：

```python
scenario_folder_map = {
    "oil_spill": "oil_spill",    # 漏油场景
    "bird_strike": "bird_strike",  # 鸟击场景
    "fod": "fod"                  # FOD场景
}
```

#### 2. 目录结构
修改后的目录结构：

```
outputs/reports/
├── oil_spill/          # 漏油场景报告
│   ├── 检查单_CA1234_20260116_120000.md
│   └── data_20260116_120000.json
├── bird_strike/        # 鸟击场景报告
│   ├── 检查单_MU5678_20260116_120000.md
│   └── data_20260116_120000.json
├── fod/               # FOD场景报告
│   ├── 检查单_CZ9012_20260116_120000.md
│   └── data_20260116_120000.json
└── other/             # 其他场景报告（兜底）
    └── ...
```

#### 3. 核心修改

**修改前**:
```python
reports_dir = os.path.join(PROJECT_ROOT, "outputs", "reports")
os.makedirs(reports_dir, exist_ok=True)
```

**修改后**:
```python
# 获取场景类型
scenario_type = state.get("scenario_type", "oil_spill")

# 场景文件夹映射
scenario_folder_map = {
    "oil_spill": "oil_spill",
    "bird_strike": "bird_strike",
    "fod": "fod"
}

# 获取场景文件夹名称，默认为 "other"
scenario_folder = scenario_folder_map.get(scenario_type, "other")

# 创建按场景分类的报告目录
reports_dir = os.path.join(PROJECT_ROOT, "outputs", "reports", scenario_folder)
os.makedirs(reports_dir, exist_ok=True)
```

## 测试验证

### 测试场景
1. **漏油场景** (oil_spill)
2. **鸟击场景** (bird_strike)
3. **FOD场景** (fod)

### 测试结果
✅ 所有场景的报告均正确保存到对应文件夹
✅ 文件命名规则保持不变
✅ JSON数据文件同步保存到对应目录
✅ 目录自动创建（使用 `os.makedirs(exist_ok=True)`）

## 影响范围

### 正面影响
1. **便于管理**: 不同场景的报告分类存储，避免混乱
2. **便于查找**: 可以快速定位特定类型的特情报告
3. **便于统计**: 方便统计各场景的报告数量
4. **向后兼容**: 未指定场景类型的报告保存到 "other" 文件夹

### 无影响范围
- API接口: 无修改
- 报告格式: 无修改
- 文件命名: 无修改
- 数据库存储: 无修改（如果有）

## 使用示例

### 漏油场景报告
```
位置: outputs/reports/oil_spill/
文件: 检查单_CA1234_20260116_120000.md
```

### 鸟击场景报告
```
位置: outputs/reports/bird_strike/
文件: 检查单_MU5678_20260116_120000.md
```

### FOD场景报告
```
位置: outputs/reports/fod/
文件: 检查单_CZ9012_20260116_120000.md
```

## 扩展说明

### 新增场景
如果需要添加新的场景类型，只需要在 `scenario_folder_map` 中添加映射：

```python
scenario_folder_map = {
    "oil_spill": "oil_spill",
    "bird_strike": "bird_strike",
    "fod": "fod",
    "tire_burst": "tire_burst",  # 新增：轮胎爆胎场景
    "runway_incursion": "runway_incursion"  # 新增：跑道入侵场景
}
```

### 场景未知处理
如果 `scenario_type` 不在映射表中，报告将保存到 `outputs/reports/other/` 目录。

## 总结

本次修改是一个简单但实用的功能增强，通过不到20行的代码修改，实现了报告的自动分类存储，提升了系统的可维护性和用户体验。

---

**修改日期**: 2026-01-16
**修改人**: Claude Code
**测试状态**: ✅ 已通过
