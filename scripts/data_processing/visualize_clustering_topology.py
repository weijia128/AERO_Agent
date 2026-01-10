"""
基于聚类的拓扑图可视化
"""
import json


def generate_clustering_visualization(topology_file: str, output_file: str):
    """生成可视化HTML"""

    # 读取拓扑图
    with open(topology_file, 'r') as f:
        graph = json.load(f)

    nodes = graph['nodes']
    edges = graph['edges']

    # 计算边界
    lats = [n['lat'] for n in nodes.values()]
    lons = [n['lon'] for n in nodes.values()]

    # 统计
    stand_count = sum(1 for n in nodes.values() if n['type'] == 'stand')
    runway_count = sum(1 for n in nodes.values() if n['type'] == 'runway')
    taxiway_count = sum(1 for n in nodes.values() if n['type'] == 'taxiway')

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>机场拓扑图 - 基于轨迹聚类（正确方法）</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 15px;
            margin-bottom: 10px;
        }}
        .method-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 20px;
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
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            transition: transform 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .stat-card .value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .legend {{
            margin: 20px 0;
            display: flex;
            gap: 25px;
            flex-wrap: wrap;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .legend-circle {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        #graph {{
            width: 100%;
            height: 900px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
        }}
        .info-box {{
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box h4 {{
            margin: 0 0 10px 0;
            color: #1976d2;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛫 机场拓扑图可视化</h1>
        <span class="method-badge">✓ 基于轨迹聚类（正确方法）</span>
        <p><strong>时段:</strong> 2025-10-21 11:00:00 - 12:00:00</p>

        <div class="info-box">
            <h4>📊 识别方法（修正版）</h4>
            <ul style="margin: 5px 0; padding-left: 20px;">
                <li><strong>机位识别:</strong> 基于位置稳定性分析（不使用速度阈值，避免混淆滑行道）</li>
                <li><strong>滑行道识别:</strong> 基于轨迹密度（速度范围：0.5-20 m/s，与机位明确区分）</li>
                <li><strong>跑道识别:</strong> 基于速度模式（速度≥30m/s的高速区域）</li>
                <li><strong>连接关系:</strong> 基于实际滑行轨迹序列</li>
            </ul>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>总节点数</h3>
                <div class="value">{len(nodes)}</div>
            </div>
            <div class="stat-card">
                <h3>机位</h3>
                <div class="value">{stand_count}</div>
                <small>基于停留时间识别</small>
            </div>
            <div class="stat-card">
                <h3>跑道</h3>
                <div class="value">{runway_count}</div>
                <small>基于速度模式识别</small>
            </div>
            <div class="stat-card">
                <h3>滑行道节点</h3>
                <div class="value">{taxiway_count}</div>
                <small>基于轨迹密度识别</small>
            </div>
            <div class="stat-card">
                <h3>连接</h3>
                <div class="value">{len(edges)}</div>
                <small>基于实际滑行轨迹</small>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #FF6B6B;"></div>
                <span><strong>机位</strong> (停留时间≥30秒)</span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #4ECDC4;"></div>
                <span><strong>跑道</strong> (速度≥30m/s)</span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #95E1D3;"></div>
                <span><strong>滑行道</strong> (轨迹密集)</span>
            </div>
            <div class="legend-item">
                <div style="width: 40px; height: 3px; background: linear-gradient(to right, #888, #333);"></div>
                <span><strong>滑行道连接</strong> (线条粗细=使用频率)</span>
            </div>
        </div>

        <div id="graph"></div>
    </div>

    <script>
        // 节点数据
        const nodes = {json.dumps(list(nodes.values()))};
        const edges = {json.dumps(edges)};

        // 按类型分组
        const standNodes = nodes.filter(n => n.type === 'stand');
        const runwayNodes = nodes.filter(n => n.type === 'runway');
        const taxiwayNodes = nodes.filter(n => n.type === 'taxiway');

        // 创建边的线段
        const edgeLines = [];
        edges.forEach(edge => {{
            const fromNode = nodes.find(n => n.id === edge.from);
            const toNode = nodes.find(n => n.id === edge.to);
            if (fromNode && toNode) {{
                const usageCount = edge.usage_count || 1;
                edgeLines.push({{
                    type: 'scatter',
                    mode: 'lines',
                    x: [fromNode.lon, toNode.lon],
                    y: [fromNode.lat, toNode.lat],
                    line: {{
                        color: usageCount > 10 ? '#333' : '#888',
                        width: Math.min(usageCount / 3, 8)
                    }},
                    hoverinfo: 'text',
                    hovertext: `${{edge.from}} ↔ ${{edge.to}}<br>距离: ${{edge.distance.toFixed(0)}}m<br>使用次数: ${{usageCount}}`,
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
                mode: 'markers',
                x: standNodes.map(n => n.lon),
                y: standNodes.map(n => n.lat),
                marker: {{
                    size: standNodes.map(n => Math.min(8 + n.observations * 2, 16)),
                    color: '#FF6B6B',
                    line: {{ color: 'white', width: 2 }},
                    opacity: 0.8
                }},
                hovertemplate: '<b>机位: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<br>观测次数: %{{marker.size}}<br>平均停留: %{{customdata:.0f}}秒<extra></extra>',
                text: standNodes.map(n => n.id),
                customdata: standNodes.map(n => n.avg_dwell_time),
                name: '机位'
            }},
            // 跑道
            {{
                type: 'scatter',
                mode: 'markers+text',
                x: runwayNodes.map(n => n.lon),
                y: runwayNodes.map(n => n.lat),
                text: runwayNodes.map(n => n.id),
                textposition: 'top center',
                marker: {{
                    size: 20,
                    symbol: 'square',
                    color: '#4ECDC4',
                    line: {{ color: 'white', width: 3 }}
                }},
                hovertemplate: '<b>跑道: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<br>平均速度: %{{customdata:.1f}} m/s<extra></extra>',
                customdata: runwayNodes.map(n => n.avg_speed),
                name: '跑道'
            }},
            // 滑行道
            {{
                type: 'scatter',
                mode: 'markers',
                x: taxiwayNodes.map(n => n.lon),
                y: taxiwayNodes.map(n => n.lat),
                marker: {{
                    size: 8,
                    color: '#95E1D3',
                    opacity: 0.6,
                    line: {{ color: 'white', width: 1 }}
                }},
                hovertemplate: '<b>滑行道: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<br>轨迹点数: %{{customdata}}<extra></extra>',
                text: taxiwayNodes.map(n => n.id),
                customdata: taxiwayNodes.map(n => n.point_count),
                name: '滑行道'
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
                yanchor: 'top',
                bgcolor: 'rgba(255,255,255,0.9)',
                bordercolor: '#ddd',
                borderwidth: 1
            }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: 'white',
            margin: {{ l: 60, r: 250, t: 40, b: 60 }}
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


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    topology_file = project_root / "scripts" / "data_processing" / "topology_clustering_based.json"
    output_file = project_root / "scripts" / "data_processing" / "topology_visualization_correct.html"

    generate_clustering_visualization(str(topology_file), str(output_file))

    print(f"\n" + "=" * 60)
    print("✓ 基于轨迹聚类的拓扑图可视化完成")
    print("=" * 60)
    print("\n特点:")
    print("- 机位: 基于停留时间识别（低速停留≥30秒）")
    print("- 跑道: 基于速度模式识别（速度≥30m/s）")
    print("- 滑行道: 基于轨迹密度识别")
    print("- 连接: 基于实际滑行轨迹序列")
    print("\n请在浏览器中打开查看")
