"""Interactive HTML Visualizer Generator for Godot Knowledge Graph.

Outputs an interactive, dark-mode visualization (graph.html)
with real-time filtering, subsystem community badges, god node highlights,
and token reduction metrics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any
import networkx as nx


def generate_html_visualization(graph: nx.DiGraph, communities: Dict[int, List[str]],
                                community_labels: Dict[int, str],
                                token_stats: Dict[str, Any],
                                output_path: Path) -> None:
    """Generate standalone interactive graph.html."""
    nodes_data = []
    
    # Reverse lookup for community ID
    node_to_comm = {}
    for cid, nids in communities.items():
        for nid in nids:
            node_to_comm[nid] = cid

    for nid in graph.nodes:
        data = graph.nodes[nid]
        cid = node_to_comm.get(nid, 0)
        cname = community_labels.get(cid, f"Subsystem {cid}")
        kind = data.get("kind", "node")
        label = data.get("label", nid)
        
        # Color coding by Godot kind
        color = "#94a3b8"
        if "autoload" in kind or "singleton" in kind:
            color = "#f59e0b"  # Amber
        elif "class" in kind:
            color = "#38bdf8"  # Light blue
        elif "scene" in kind:
            color = "#10b981"  # Emerald green
        elif "signal" in kind:
            color = "#f97316"  # Orange
        elif "func" in kind or "handler" in kind:
            color = "#a855f7"  # Purple
        elif "export" in kind or "var" in kind:
            color = "#ec4899"  # Pink

        nodes_data.append({
            "id": nid,
            "label": label,
            "kind": kind,
            "color": color,
            "community_id": cid,
            "community_name": cname,
            "source_file": data.get("source_file", ""),
            "source_location": data.get("source_location", ""),
            "degree": graph.degree(nid),
        })

    edges_data = []
    for src, tgt, edata in graph.edges(data=True):
        rel = edata.get("relation", "relates_to")
        edges_data.append({
            "source": src,
            "target": tgt,
            "relation": rel,
            "weight": edata.get("weight", 1.0),
            "context": edata.get("context", ""),
            "confidence": edata.get("confidence", "EXTRACTED"),
        })

    raw_tokens = token_stats.get("estimated_raw_tokens", 85000)
    avg_query_tokens = 1250
    saved_tokens = max(raw_tokens - avg_query_tokens, 0)
    saved_pct = round((saved_tokens / max(raw_tokens, 1)) * 100, 1)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Godot GDScript Knowledge Graph - Graphify</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: rgba(30, 41, 59, 0.85);
            --border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.25);
            --gold: #f59e0b;
            --emerald: #10b981;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            overflow: hidden;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 10;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .brand-badge {{
            background: linear-gradient(135deg, #478cbf, #38bdf8);
            color: white;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 13px;
            letter-spacing: 0.5px;
        }}
        .brand-title {{
            font-size: 18px;
            font-weight: 700;
        }}
        .token-savings-badge {{
            display: flex;
            align-items: center;
            gap: 16px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.4);
            padding: 6px 16px;
            border-radius: 9999px;
            font-size: 13px;
        }}
        .stat-pill strong {{
            color: #34d399;
        }}
        .main-container {{
            flex: 1;
            position: relative;
            display: flex;
        }}
        #network {{
            flex: 1;
            height: 100%;
            background: radial-gradient(circle at 50% 50%, #1e293b 0%, #0f172a 100%);
        }}
        .sidebar {{
            position: absolute;
            top: 16px;
            left: 16px;
            width: 320px;
            max-height: calc(100% - 32px);
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            z-index: 20;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            overflow-y: auto;
        }}
        .search-input {{
            width: 100%;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
            color: var(--text-primary);
            font-size: 13px;
            outline: none;
        }}
        .search-input:focus {{
            border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent-glow);
        }}
        .legend {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 12px;
            margin-top: 4px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}
        .inspector {{
            position: absolute;
            top: 16px;
            right: 16px;
            width: 340px;
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            z-index: 20;
            display: none;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .inspector-title {{
            font-size: 16px;
            font-weight: 700;
            color: var(--accent);
            word-break: break-all;
            margin-bottom: 8px;
        }}
        .inspector-meta {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 12px;
            line-height: 1.5;
        }}
        .inspector-connections {{
            font-size: 12px;
            border-top: 1px solid var(--border);
            padding-top: 10px;
            max-height: 250px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <span class="brand-badge">GODOT 4</span>
            <span class="brand-title">Graphify GDScript Architecture Graph</span>
        </div>
        <div class="token-savings-badge">
            <span class="stat-pill">Project Raw Tokens: <strong>~{raw_tokens:,}</strong></span>
            <span>&rarr;</span>
            <span class="stat-pill">Target Context: <strong>~{avg_query_tokens:,}</strong></span>
            <span class="stat-pill">Token Reduction: <strong>{saved_pct}% SAVED</strong></span>
        </div>
    </header>

    <div class="main-container">
        <div class="sidebar">
            <h3 style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-secondary);">Controls & Filters</h3>
            <input type="text" id="searchInput" class="search-input" placeholder="Search classes, signals, scenes, methods...">
            
            <h4 style="font-size: 13px; font-weight: 600; margin-top: 6px;">Entity Color Legend</h4>
            <div class="legend">
                <div class="legend-item"><span class="legend-dot" style="background:#f59e0b;"></span> Autoload</div>
                <div class="legend-item"><span class="legend-dot" style="background:#38bdf8;"></span> Class</div>
                <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> Scene</div>
                <div class="legend-item"><span class="legend-dot" style="background:#f97316;"></span> Signal</div>
                <div class="legend-item"><span class="legend-dot" style="background:#a855f7;"></span> Method</div>
                <div class="legend-item"><span class="legend-dot" style="background:#ec4899;"></span> Property</div>
            </div>

            <h4 style="font-size: 13px; font-weight: 600; margin-top: 10px;">Subsystem Communities</h4>
            <div id="communityList" style="font-size: 12px; display: flex; flex-direction: column; gap: 6px;">
                {"".join(f'<div style="padding: 4px 8px; background: rgba(255,255,255,0.05); border-radius: 4px;">• {cname} ({len(communities[cid])} nodes)</div>' for cid, cname in community_labels.items())}
            </div>
        </div>

        <div id="network"></div>

        <div id="inspector" class="inspector">
            <div id="inspectorTitle" class="inspector-title">Node Info</div>
            <div id="inspectorMeta" class="inspector-meta"></div>
            <div class="inspector-connections">
                <strong>Active Edges:</strong>
                <ul id="inspectorEdges" style="list-style: none; margin-top: 6px;"></ul>
            </div>
        </div>
    </div>

    <script>
        const nodesData = {json.dumps(nodes_data)};
        const edgesData = {json.dumps(edges_data)};

        const nodes = new vis.DataSet(nodesData.map(n => ({{
            id: n.id,
            label: n.label,
            color: {{ background: n.color, border: '#ffffff', highlight: {{ background: '#ffffff', border: n.color }} }},
            shape: n.kind === 'autoload_singleton' ? 'hexagon' : (n.kind === 'scene' ? 'box' : 'dot'),
            size: Math.max(14, Math.min(32, 14 + n.degree * 2)),
            font: {{ color: '#f8fafc', size: 12 }},
            data: n
        }})));

        const edges = new vis.DataSet(edgesData.map(e => ({{
            from: e.source,
            to: e.target,
            label: e.relation,
            arrows: 'to',
            color: {{ color: '#475569', highlight: '#38bdf8' }},
            font: {{ color: '#94a3b8', size: 9, align: 'middle' }},
            smooth: {{ type: 'continuous' }}
        }})));

        const container = document.getElementById('network');
        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            nodes: {{ borderWidth: 1 }},
            edges: {{ arrows: {{ to: {{ enabled: true, scaleFactor: 0.7 }} }} }},
            physics: {{
                stabilization: true,
                barnesHut: {{ gravitationalConstant: -3000, springLength: 95 }}
            }},
            interaction: {{ hover: true, tooltipDelay: 100 }}
        }};

        const network = new vis.Network(container, data, options);

        // Click inspector
        network.on('click', function(params) {{
            const inspector = document.getElementById('inspector');
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const nodeItem = nodesData.find(n => n.id === nodeId);
                if (nodeItem) {{
                    document.getElementById('inspectorTitle').innerText = nodeItem.label;
                    document.getElementById('inspectorMeta').innerHTML = 
                        `<strong>Kind:</strong> ${{nodeItem.kind}}<br>` +
                        `<strong>Subsystem:</strong> ${{nodeItem.community_name}}<br>` +
                        `<strong>Source:</strong> ${{nodeItem.source_file}} (${{nodeItem.source_location}})<br>` +
                        `<strong>Total Connections:</strong> ${{nodeItem.degree}}`;

                    const connected = edgesData.filter(e => e.source === nodeId || e.target === nodeId);
                    const list = document.getElementById('inspectorEdges');
                    list.innerHTML = connected.map(e => 
                        `<li style="padding: 2px 0;">${{e.source === nodeId ? '&rarr;' : '&larr;'}} <strong>${{e.relation}}</strong> ${{e.source === nodeId ? e.target : e.source}}</li>`
                    ).join('');

                    inspector.style.display = 'block';
                }}
            }} else {{
                inspector.style.display = 'none';
            }}
        }});

        // Search filter
        document.getElementById('searchInput').addEventListener('input', function(e) {{
            const q = e.target.value.toLowerCase().trim();
            if (!q) {{
                nodes.forEach(n => nodes.update({{ id: n.id, hidden: false }}));
                return;
            }}
            nodes.forEach(n => {{
                const match = n.label.toLowerCase().includes(q) || n.data.kind.toLowerCase().includes(q);
                nodes.update({{ id: n.id, hidden: !match }});
            }});
        }});
    </script>
</body>
</html>"""
    output_path.write_text(html_content, encoding="utf-8")
