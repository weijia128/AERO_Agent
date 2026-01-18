"""
基于机场平面图生成的拓扑图可视化
"""
import json
from pathlib import Path


def generate_map_visualization(topology_file: str, output_file: str):
    with open(topology_file, "r", encoding="utf-8") as f:
        graph = json.load(f)

    nodes = graph["nodes"]
    edges = graph["edges"]

    lats = [n["lat"] for n in nodes.values()]
    lons = [n["lon"] for n in nodes.values()]

    stand_count = sum(1 for n in nodes.values() if n["type"] == "stand")
    runway_count = sum(1 for n in nodes.values() if n["type"] == "runway")
    taxiway_count = sum(1 for n in nodes.values() if n["type"] == "taxiway")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>机场拓扑图 - 基于机场平面图</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
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
            border-bottom: 3px solid #2c5364;
            padding-bottom: 15px;
            margin-bottom: 10px;
        }}
        .method-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #0f2027 0%, #2c5364 100%);
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
            background: linear-gradient(135deg, #0f2027 0%, #2c5364 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
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
            background: #e8f5e9;
            border-left: 4px solid #2e7d32;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box h4 {{
            margin: 0 0 10px 0;
            color: #2e7d32;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛫 机场拓扑图可视化</h1>
        <span class="method-badge">✓ 基于机场平面图</span>
        <p><strong>数据源:</strong> Standno/TaxiRoad shapefile</p>

        <div class="info-box">
            <h4>📊 构建方法</h4>
            <ul style="margin: 5px 0; padding-left: 20px;">
                <li><strong>机位节点:</strong> Standno_Self_Property.shp 的 POINT_X/POINT_Y</li>
                <li><strong>滑行道节点:</strong> TaxiRoad.shp 的 RoadName 分段中心点</li>
                <li><strong>跑道节点:</strong> 路径字段中的 05L/23R 等标识</li>
                <li><strong>连接关系:</strong> 机位路径字段 path_* 的序列连接</li>
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
            </div>
            <div class="stat-card">
                <h3>跑道</h3>
                <div class="value">{runway_count}</div>
            </div>
            <div class="stat-card">
                <h3>滑行道节点</h3>
                <div class="value">{taxiway_count}</div>
            </div>
            <div class="stat-card">
                <h3>连接</h3>
                <div class="value">{len(edges)}</div>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #FF6B6B;"></div>
                <span><strong>机位</strong></span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #4ECDC4;"></div>
                <span><strong>跑道</strong></span>
            </div>
            <div class="legend-item">
                <div class="legend-circle" style="background-color: #95E1D3;"></div>
                <span><strong>滑行道</strong></span>
            </div>
            <div class="legend-item">
                <div style="width: 40px; height: 3px; background: linear-gradient(to right, #888, #333);"></div>
                <span><strong>连接</strong> (线条粗细=出现频次)</span>
            </div>
        </div>

        <div id="graph"></div>
    </div>

    <script>
        const nodes = {json.dumps(list(nodes.values()))};
        const edges = {json.dumps(edges)};

        const standNodes = nodes.filter(n => n.type === 'stand');
        const runwayNodes = nodes.filter(n => n.type === 'runway');
        const taxiwayNodes = nodes.filter(n => n.type === 'taxiway');

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
                        width: Math.min(edge.usage_count / 2, 6)
                    }},
                    hoverinfo: 'text',
                    hovertext: `${{edge.from}} ↔ ${{edge.to}}<br>距离: ${{edge.distance.toFixed(0)}}m<br>出现次数: ${{edge.usage_count}}`,
                    showlegend: false
                }});
            }}
        }});

        const traces = [
            ...edgeLines,
            {{
                type: 'scatter',
                mode: 'markers+text',
                x: standNodes.map(n => n.lon),
                y: standNodes.map(n => n.lat),
                text: standNodes.map(n => n.id.replace('stand_', '')),
                textposition: 'top center',
                marker: {{
                    size: 10,
                    color: '#FF6B6B',
                    line: {{ color: 'white', width: 1 }}
                }},
                hovertemplate: '<b>机位: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<extra></extra>',
                name: '机位'
            }},
            {{
                type: 'scatter',
                mode: 'markers+text',
                x: runwayNodes.map(n => n.lon),
                y: runwayNodes.map(n => n.lat),
                text: runwayNodes.map(n => n.id.replace('runway_', '')),
                textposition: 'bottom center',
                marker: {{
                    size: 12,
                    color: '#4ECDC4',
                    line: {{ color: 'white', width: 1 }}
                }},
                hovertemplate: '<b>跑道: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<extra></extra>',
                name: '跑道'
            }},
            {{
                type: 'scatter',
                mode: 'markers',
                x: taxiwayNodes.map(n => n.lon),
                y: taxiwayNodes.map(n => n.lat),
                marker: {{
                    size: 5,
                    color: '#95E1D3',
                    line: {{ color: 'white', width: 0.5 }}
                }},
                hovertemplate: '<b>滑行道: %{{text}}</b><br>坐标: (%{{y:.5f}}, %{{x:.5f}})<extra></extra>',
                text: taxiwayNodes.map(n => n.id.replace('taxiway_', '')),
                name: '滑行道'
            }}
        ];

        const layout = {{
            title: '',
            showlegend: true,
            xaxis: {{
                title: '经度',
                range: [{min(lons)}, {max(lons)}]
            }},
            yaxis: {{
                title: '纬度',
                range: [{min(lats)}, {max(lats)}]
            }},
            height: 900,
            hovermode: 'closest'
        }};

        Plotly.newPlot('graph', traces, layout);
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Visualization saved: {output_file}")


def main():
    project_root = Path(__file__).resolve().parents[2]
    topology_file = project_root / "scripts" / "data_processing" / "topology_map_based.json"
    output_file = project_root / "scripts" / "data_processing" / "topology_visualization_map_based.html"
    generate_map_visualization(str(topology_file), str(output_file))


if __name__ == "__main__":
    main()
