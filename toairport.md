项目前端地理信息地图技术分析

  基于对代码的深入分析，该项目前端地理信息可视化采用了以下技术栈和库：

  🗺️ 核心地图引擎

  Leaflet - 主要地图库
   - 版本：^1.9.4
   - 用途：作为核心地图渲染引擎，负责底图展示、图层管理和交互控制
   - 初始化位置：北京首都机场区域（中心点：[40.08, 116.58]）

  📦 Leaflet 插件生态

   1. leaflet-polylinedecorator (^1.6.0)
      - 用途：在流线上绘制箭头装饰，表示事件传播方向

   2. leaflet.heat (^0.2.0)
      - 用途：生成风险热力图，可视化SES事件密度

   3. leaflet-curve (^1.0.0)
      - 用途：绘制曲线连接线，美化级联事件间的视觉关联

  🎯 地理空间数据处理库

   1. @turf/turf (^7.2.0)
      - 用途：地理空间分析计算，如距离、缓冲区、聚合等

   2. @terraformer/wkt (^2.2.1) + wellknown (^0.5.0)
      - 用途：解析WKT（Well-Known Text）格式的地理坐标

   3. shpjs (^6.1.0)
      - 用途：读取和处理Shapefile格式地理数据

   4. utm (^1.1.1)
      - 用途：UTM坐标与经纬度之间的转换（项目使用UTM Zone 50N）

  🎨 可视化与样式

   1. D3.js (^7.9.0)
      - 用途：数据驱动的可视化，用于颜色比例尺、地理数据处理
      - 在地图中主要用于：风险色阶计算、数据聚合

   2. 自定义配色系统 (src/styles/colorScheme.js)
      - 采用Tailwind CSS色板
      - 语义化配色方案：
        - 空间/物理层：冷色系（蓝灰色）
        - 事件/交互层：青色系
        - 风险/CSI层：红绿渐变
        - 飞机/Agent层：紫色系

  📊 数据格式

   - GeoJSON：主路数据、机场地图（跑道/滑行道）
   - CSV：SES事件日志、级联数据
   - WKT：事件点坐标存储格式
   - 自定义JSON：速度曲线、轨迹片段

  🏗️ 架构设计

  核心组件：
   - GeospatialMapView.vue：主地图组件（src/components/GeospatialMapView.vue:1）
   - AnalysisLayout.vue：L型布局容器（src/layouts/AnalysisLayout.vue:1）

  工具模块：
   - mapLayers.js：图层创建工厂（热力图、节点、流线等）
   - coordinateUtils.js：坐标转换工具
   - dataLoader.js：地理数据加载器

  图层管理：
  使用Leaflet的Pane系统控制绘制顺序：
   - mainRoutes (zIndex: 405) - 主路背景
   - flows (zIndex: 410) - 流线
   - arrows (zIndex: 420) - 箭头
   - highlight (zIndex: 425) - 高亮
   - nodes (zIndex: 430) - 关键节点
   - trajectoryFragments (zIndex: 650) - 轨迹片段（最顶层）