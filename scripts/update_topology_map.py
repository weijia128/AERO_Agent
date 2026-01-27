#!/usr/bin/env python3
"""
自动更新前端拓扑地图脚本

用法:
    python scripts/update_topology_map.py <新拓扑HTML路径>

功能:
    1. 复制新的拓扑HTML到前端public目录
    2. 自动添加高亮功能代码（读取URL参数、节点高亮、状态显示）
    3. 添加图例说明
"""

import sys
import re
from pathlib import Path


def add_highlight_code(content: str) -> str:
    """添加高亮代码到HTML"""

    # 1. 添加URL参数读取和高亮逻辑
    highlight_code = '''        // 【新增】读取URL参数并高亮对应节点
        const urlParams = new URLSearchParams(window.location.search);
        const incidentNode = urlParams.get('incident');
        const affectedStands = urlParams.get('affected_stands')?.split(',').filter(Boolean) || [];
        const affectedTaxiways = urlParams.get('affected_taxiways')?.split(',').filter(Boolean).map(id => 'taxiway_' + id) || [];
        const affectedRunways = urlParams.get('affected_runways')?.split(',').filter(Boolean).map(id => 'runway_' + id) || [];

        // 通过name定位各个trace并应用高亮
        traces.forEach((trace, idx) => {
            // 高亮机位
            if (trace.name === '机位') {
                const colors = trace.x.map((_, i) => {
                    const nodeId = standNodes[i]?.id;
                    if (nodeId === incidentNode) return '#DC143C'; // 深红色 - 事发位置
                    if (affectedStands.includes(nodeId)) return '#FFA500'; // 橙色 - 受影响
                    return '#FF6B6B'; // 默认红色
                });
                const sizes = trace.x.map((_, i) => {
                    const nodeId = standNodes[i]?.id;
                    if (nodeId === incidentNode) return 18; // 事发位置更大
                    if (affectedStands.includes(nodeId)) return 14; // 受影响稍大
                    return 10; // 默认大小
                });
                trace.marker = {
                    ...trace.marker,
                    color: colors,
                    size: sizes,
                    line: { color: 'white', width: 1.5 }
                };
            }
            // 高亮跑道
            else if (trace.name === '跑道') {
                const colors = trace.x.map((_, i) => {
                    const nodeId = runwayNodes[i]?.id;
                    if (affectedRunways.includes(nodeId)) return '#FFD700'; // 金黄色 - 受影响
                    return '#4ECDC4'; // 默认青色
                });
                const sizes = trace.x.map((_, i) => {
                    const nodeId = runwayNodes[i]?.id;
                    if (affectedRunways.includes(nodeId)) return 16; // 受影响稍大
                    return 12; // 默认大小
                });
                trace.marker = {
                    ...trace.marker,
                    color: colors,
                    size: sizes,
                    line: { color: 'white', width: 1.5 }
                };
            }
            // 高亮滑行道
            else if (trace.name === '滑行道') {
                const colors = trace.x.map((_, i) => {
                    const nodeId = taxiwayNodes[i]?.id;
                    if (affectedTaxiways.includes(nodeId)) return '#FFD700'; // 金黄色 - 受影响
                    return '#95E1D3'; // 默认浅青色
                });
                const sizes = trace.x.map((_, i) => {
                    const nodeId = taxiwayNodes[i]?.id;
                    if (affectedTaxiways.includes(nodeId)) return 8; // 受影响稍大
                    return 5; // 默认大小
                });
                trace.marker = {
                    ...trace.marker,
                    color: colors,
                    size: sizes,
                    line: { color: 'white', width: 1 }
                };
            }
        });

'''

    # 在 Plotly.newPlot 之前插入高亮代码
    content = content.replace(
        "        Plotly.newPlot('graph', traces, layout);",
        highlight_code + "        Plotly.newPlot('graph', traces, layout);"
    )

    # 2. 添加状态显示框
    status_code = '''

        // 显示当前高亮状态
        if (incidentNode || affectedStands.length > 0 || affectedTaxiways.length > 0 || affectedRunways.length > 0) {
            const statusDiv = document.createElement('div');
            statusDiv.style.cssText = 'position: absolute; top: 20px; right: 20px; background: rgba(255,255,255,0.95); border: 2px solid #2c5364; border-radius: 10px; padding: 15px; max-width: 300px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 1000;';

            let statusHTML = '<h4 style="margin: 0 0 10px 0; color: #2c5364; font-size: 14px;">📍 当前高亮状态</h4>';

            if (incidentNode) {
                statusHTML += '<div style="margin-bottom: 8px;"><strong style="color: #DC143C;">🔴 事发位置:</strong> ' + incidentNode + '</div>';
            }

            if (affectedStands.length > 0) {
                statusHTML += '<div style="margin-bottom: 8px;"><strong style="color: #FFA500;">🟠 受影响机位:</strong> ' + affectedStands.length + ' 个</div>';
            }

            if (affectedTaxiways.length > 0) {
                statusHTML += '<div style="margin-bottom: 8px;"><strong style="color: #FFD700;">🟡 受影响滑行道:</strong> ' + affectedTaxiways.length + ' 个</div>';
            }

            if (affectedRunways.length > 0) {
                statusHTML += '<div style="margin-bottom: 8px;"><strong style="color: #FFD700;">🟡 受影响跑道:</strong> ' + affectedRunways.length + ' 个</div>';
            }

            statusDiv.innerHTML = statusHTML;
            document.getElementById('graph').parentElement.style.position = 'relative';
            document.getElementById('graph').parentElement.appendChild(statusDiv);
        }
'''

    content = content.replace(
        "        Plotly.newPlot('graph', traces, layout);",
        "        Plotly.newPlot('graph', traces, layout);" + status_code
    )

    # 3. 添加图例说明
    legend_html = '''
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #DC143C;"></div>
                <span><strong>事发位置</strong></span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #FFA500;"></div>
                <span><strong>受影响机位</strong></span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #FFD700;"></div>
                <span><strong>受影响跑道/滑行道</strong></span>
            </div>'''

    # 查找图例结束位置并插入
    content = content.replace(
        '            </div>\n        </div>\n\n        <div id="graph"></div>',
        '            </div>' + legend_html + '\n        </div>\n\n        <div id="graph"></div>'
    )

    return content


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/update_topology_map.py <新拓扑HTML路径>")
        print("示例: python scripts/update_topology_map.py scripts/data_processing/topology_visualization_map_based.html")
        sys.exit(1)

    # 路径配置
    source_path = Path(sys.argv[1])
    target_path = Path(__file__).parent.parent / "frontend" / "public" / "topology_map.html"

    # 检查源文件
    if not source_path.exists():
        print(f"❌ 错误: 找不到源文件: {source_path}")
        sys.exit(1)

    # 读取源文件
    print(f"📖 读取拓扑HTML: {source_path}")
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 添加高亮功能
    print("✨ 添加高亮功能代码...")
    content = add_highlight_code(content)

    # 写入目标文件
    print(f"💾 保存到: {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ 拓扑地图更新成功！")
    print(f"📊 文件大小: {len(content) / 1024:.1f} KB")
    print("\n🚀 下一步:")
    print("   1. 刷新前端页面查看效果")
    print("   2. 测试URL参数: http://localhost:5173/topology_test.html")


if __name__ == "__main__":
    main()
