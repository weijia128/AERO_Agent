# 机场拓扑从 data/raw 生成说明

本文说明如何基于 `data/raw/机场平面图` 的机场图数据生成当前机场拓扑信息。

## 入口与脚本

- 脚本：`scripts/data_processing/build_topology_from_airport_map.py`
- 输入：
  - `data/raw/机场平面图/Standno/Standno_Self_Property.shp`
  - `data/raw/机场平面图/TaxiRoad/TaxiRoad.shp`
- 输出：`scripts/data_processing/topology_map_based.json`

## 核心流程概述

1. 读取机位点（Stand）
   - 从 `Standno_Self_Property.shp` 读取 `code/NAME/POINT_X/POINT_Y`。
   - 生成 `stand_XXX` 节点；坐标为 UTM，后续转换为经纬度。

2. 读取滑行道/跑道线（TaxiRoad）
   - 从 `TaxiRoad.shp` 读取 `RoadName` 与线坐标。
   - `RoadName` 按 `-` 切分为 token，统一大小写，并识别包含“跑道”的 token 提示。

3. 跑道命名归一化
   - 将方向对（如 `05L/23R`）合并为同一跑道 token（`05L_23R`），避免拓扑重复。

4. 构建节点
   - 机位节点：由 Stand 点直接生成。
   - 滑行道/跑道节点：由 `RoadName` token 生成，节点类型根据是否为跑道判断。
   - 节点坐标：按该 token 对应线的平均坐标求中心点。

5. 构建边（连接关系）
   - 机位路径：读取 Stand 表内 `path_*` 字段，把机位与路径 token 顺序相连。
   - 线内连接：对 `RoadName` 内部 token 做顺序连接（如 `A5-A`）。
   - 几何补连：对单一 token 的线段做几何相交/近距（1m 容差）连接。
   - 保守补全：
     - 孤立滑行道：与最近滑行道线段距离 <= 25m 时连接。
     - 孤立机位：与最近滑行道节点距离 <= 40m 时连接。

6. 坐标补全
   - 若某节点缺坐标，先用邻接节点平均值补齐。
   - 仍缺失则使用全局质心兜底。

7. 输出拓扑
   - 输出 `nodes`（含 `id/type/lat/lon`）与 `edges`（含 `from/to/distance/usage_count`）。

## 备注

- 坐标转换：脚本内使用 `utm_to_latlon` 将 UTM 转为经纬度。
- 结果文件：`scripts/data_processing/topology_map_based.json` 可被拓扑加载器或空间工具直接读取。
