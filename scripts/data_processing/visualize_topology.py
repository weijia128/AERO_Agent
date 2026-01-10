"""
拓扑图可视化工具

生成交互式HTML可视化，展示：
- 机位位置
- 跑道位置
- 滑行道连接
- 交叉点
"""
import json
from pathlib import Path


class TopologyVisualizer:
    """拓扑图可视化器"""

    def generate_html(self, topology_file: str, output_file: str):
        """
        生成交互式HTML可视化

        Args:
            topology_file: 拓扑图JSON文件
            output_file: 输出HTML文件路径
        """
        # 读取拓扑图
        with open(topology_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        graph = data['graph']
        nodes = graph['nodes']
        edges = graph['edges']

        # 计算边界
        lats = [n['lat'] for n in nodes.values()]
        lons = [n['lon'] for n in nodes.values()]
        center_lat = (max(lats) + min(lats)) / 2
        center_lon = (max(lons) + min(lons)) / 2

        # 生成HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>机场拓扑图 - 2025-10-21 11:00-12:00</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .stat-card .value {{
            font-size: 32px;
            font-weight: bold;
        }}
        .legend {{
            margin: 20px 0;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-circle {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        #graph {{
            width: 100%;
            height: 800px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛫 机场拓扑图可视化</h1>
        <p>时段: 2025-10-21 11:00:00 - 12:00:00</p>

        <div class="stats">
            <div class="stat-card">
                <h3>总节点数</h3>
                <div class="value">{len(nodes)}</div>
            </div>
            <div class="stat-card">
                <h3>机位</h3>
                <div class="value">{sum(1 for n in nodes.values() if n['type'] == 'stand')}</div>
            </div>
            <div class="stat-card">
                <h3>跑道</h3>
                <div class="value">{sum(1 for n in nodes.values() if n['type'] == 'runway')}</div>
            </div>
            <div class="stat-card">
                <h3>交叉点</h3>
                <div class="value">{sum(1 for n in nodes.values() if n['type'] == 'intersection')}</div>
            </div>
            <div class="stat-card">
                <h3>滑行道连接</h3>
                <div class="value">{len(edges)}</div>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #FF6B6B;"></div>
                <span>机位</span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #4ECDC4;"></div>
                <span>跑道</span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #95E1D3;"></div>
                <span>交叉点</span>
            </div>
            <div class="legend-item">
                <div style="width: 30px; height: 2px; background-color: #888;"></div>
                <span>滑行道</span>
            </div>
        </div>

        <div id="graph"></div>
    </div>

    <script>
        // 节点数据
        const nodes = {json.dumps(list(nodes.values()))};

        // 边数据
        const edges = {json.dumps(edges)};

        // 按类型分组节点
        const standNodes = nodes.filter(n => n.type === 'stand');
        const runwayNodes = nodes.filter(n => n.type === 'runway');
        const intersectionNodes = nodes.filter(n => n.type === 'intersection');

        // 创建边的线段
        const edgeLines = [];
        edges.forEach(edge => {{
            const fromNode = nodes.find(n => n.id === edge.from);
            const toNode = nodes.find(n => n.id === edge.to);
            if (fromNode && toNode) {{
                edgeLines.push({{
                    type: 'scatter',
                    mode: 'lines',
                    x: [fromNode.lon, toNode.lon],
                    y: [fromNode.lat, toNode.lat],
                    line: {{
                        color: '#888',
                        width: Math.min(edge.usage_count / 2, 5)
                    }},
                    hoverinfo: 'text',
                    hovertext: `${{edge.from}} ↔ ${{edge.to}}<br>距离: ${{edge.distance.toFixed(0)}}m<br>使用次数: ${{edge.usage_count}}`,
                    showlegend: false
                }});
            }}
        }});

        // 创建图形数据
        const traces = [
            ...edgeLines,
            // 机位
            {{
                type: 'scatter',
                mode: 'markers+text',
                x: standNodes.map(n => n.lon),
                y: standNodes.map(n => n.lat),
                text: standNodes.map(n => n.stand_name),
                textposition: 'top center',
                marker: {{
                    size: 12,
                    color: '#FF6B6B',
                    line: {{ color: 'white', width: 2 }}
                }},
                hovertemplate: '<b>机位: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<extra></extra>',
                name: '机位'
            }},
            // 跑道
            {{
                type: 'scatter',
                mode: 'markers+text',
                x: runwayNodes.map(n => n.lon),
                y: runwayNodes.map(n => n.lat),
                text: runwayNodes.map(n => n.runway_name),
                textposition: 'bottom center',
                marker: {{
                    size: 16,
                    symbol: 'square',
                    color: '#4ECDC4',
                    line: {{ color: 'white', width: 2 }}
                }},
                hovertemplate: '<b>跑道: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<extra></extra>',
                name: '跑道'
            }},
            // 交叉点
            {{
                type: 'scatter',
                mode: 'markers',
                x: intersectionNodes.map(n => n.lon),
                y: intersectionNodes.map(n => n.lat),
                marker: {{
                    size: 6,
                    color: '#95E1D3',
                    opacity: 0.6
                }},
                hovertemplate: '<b>交叉点</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<extra></extra>',
                name: '交叉点'
            }}
        ];

        // 布局配置
        const layout = {{
            title: '',
            xaxis: {{
                title: '经度',
                gridcolor: '#e0e0e0',
                zeroline: false
            }},
            yaxis: {{
                title: '纬度',
                gridcolor: '#e0e0e0',
                zeroline: false,
                scaleanchor: 'x',
                scaleratio: 1
            }},
            hovermode: 'closest',
            showlegend: true,
            legend: {{
                x: 1.02,
                y: 1,
                xanchor: 'left',
                yanchor: 'top'
            }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: 'white',
            margin: {{ l: 60, r: 200, t: 40, b: 60 }}
        }};

        // 配置选项
        const config = {{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        }};

        // 渲染图形
        Plotly.newPlot('graph', traces, layout, config);
    </script>
</body>
</html>
"""

        # 保存HTML
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"\n✓ 可视化已生成: {output_file}")
        print(f"  请在浏览器中打开查看")


if __name__ == "__main__":
    visualizer = TopologyVisualizer()

    project_root = Path(__file__).resolve().parents[2]
    topology_file = project_root / "scripts" / "data_processing" / "airport_topology_11_12.json"
    output_file = project_root / "scripts" / "data_processing" / "topology_visualization.html"

    visualizer.generate_html(str(topology_file), str(output_file))

    print(f"\n" + "=" * 60)
    print("可视化说明")
    print("=" * 60)
    print("- 红色圆点: 机位")
    print("- 青色方块: 跑道")
    print("- 浅绿色小点: 滑行道交叉点")
    print("- 灰色线条: 滑行道连接（线条粗细表示使用频率）")
    print("\n鼠标悬停可查看详细信息，可缩放和平移查看")
