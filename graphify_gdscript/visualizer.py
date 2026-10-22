"""Interactive HTML Visualizer Generator for Godot Knowledge Graph.

Outputs an interactive, dark-mode visualization (graph.html)
with real-time filtering, subsystem community badges, god node highlights,
and token reduction metrics.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, List, Any
import networkx as nx

# Pinned so a new vis-network major release cannot silently break the page; the
# integrity hash is the same file on both CDNs, tried in order.
VIS_NETWORK_URLS = [
    "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js",
    "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js",
]
VIS_NETWORK_SRI = "sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ"


def _script_json(value: Any) -> str:
    """JSON safe to inline in a <script> block (a "</script>" in a label cannot end it)."""
    return json.dumps(value).replace("</", "<\\/")


def generate_html_visualization(graph: nx.DiGraph, communities: Dict[int, List[str]],
                                community_labels: Dict[int, str],
                                token_stats: Dict[str, Any],
                                output_path: Path) -> None:
    """Generate standalone interactive graph.html.

    ``token_stats`` takes the builder stats; an optional ``query_tokens`` entry (the size
    of a typical graph query) drives the savings banner.
    """
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
    query_tokens = token_stats.get("query_tokens") or 1250
    saved_tokens = max(raw_tokens - query_tokens, 0)
    saved_pct = round((saved_tokens / max(raw_tokens, 1)) * 100, 1)

    community_items = "".join(
        f'<div class="community-item">&bull; {html.escape(cname)} ({len(communities.get(cid, []))} nodes)</div>'
        for cid, cname in community_labels.items()
    )

    replacements = {
        "__RAW_TOKENS__": f"{raw_tokens:,}",
        "__QUERY_TOKENS__": f"{query_tokens:,}",
        "__SAVED_PCT__": str(saved_pct),
        "__COMMUNITY_ITEMS__": community_items,
        "__NODES_JSON__": _script_json(nodes_data),
        "__EDGES_JSON__": _script_json(edges_data),
        "__VIS_URLS_JSON__": _script_json(VIS_NETWORK_URLS),
        "__VIS_SRI_JSON__": _script_json(VIS_NETWORK_SRI),
    }
    page = _TEMPLATE
    for token, value in replacements.items():
        page = page.replace(token, value)
    output_path.write_text(page, encoding="utf-8")


# Plain string (not an f-string) so the CSS and JavaScript braces stay readable;
# __PLACEHOLDERS__ are filled in by generate_html_visualization.
_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Godot GDScript Knowledge Graph - Graphify</title>
    <style>
        :root {
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
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            overflow: hidden;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
            z-index: 10;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-badge {
            background: linear-gradient(135deg, #478cbf, #38bdf8);
            color: white;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 13px;
            letter-spacing: 0.5px;
        }
        .brand-title {
            font-size: 18px;
            font-weight: 700;
        }
        .token-savings-badge {
            display: flex;
            align-items: center;
            gap: 16px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.4);
            padding: 6px 16px;
            border-radius: 9999px;
            font-size: 13px;
        }
        .stat-pill strong {
            color: #34d399;
        }
        /* The graph fills whatever space the header leaves. min-height: 0 and the
           absolutely positioned #network keep the canvas out of flex sizing: otherwise
           the canvas height feeds back into the container, which grows on every
           redraw and pushes the graph below the visible area. */
        .main-container {
            flex: 1;
            min-height: 0;
            position: relative;
            overflow: hidden;
        }
        #network {
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at 50% 50%, #1e293b 0%, #0f172a 100%);
        }
        .status {
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            max-width: 460px;
            padding: 14px 20px;
            border-radius: 10px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            font-size: 13px;
            line-height: 1.5;
            text-align: center;
            z-index: 15;
        }
        .status.error {
            color: #fecaca;
            border-color: #b91c1c;
        }
        .sidebar {
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
        }
        .search-input {
            width: 100%;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
            color: var(--text-primary);
            font-size: 13px;
            outline: none;
        }
        .search-input:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent-glow);
        }
        .legend {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 12px;
            margin-top: 4px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .community-item {
            padding: 4px 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        .inspector {
            position: absolute;
            top: 16px;
            right: 16px;
            width: 340px;
            max-height: calc(100% - 32px);
            overflow-y: auto;
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            z-index: 20;
            display: none;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }
        .inspector-title {
            font-size: 16px;
            font-weight: 700;
            color: var(--accent);
            word-break: break-all;
            margin-bottom: 8px;
        }
        .inspector-meta {
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 12px;
            line-height: 1.5;
            word-break: break-all;
        }
        .inspector-connections {
            font-size: 12px;
            border-top: 1px solid var(--border);
            padding-top: 10px;
            max-height: 250px;
            overflow-y: auto;
        }
        @media (max-width: 720px) {
            .sidebar { width: auto; right: 16px; max-height: 40%; }
            .inspector { width: auto; left: 16px; top: auto; bottom: 16px; max-height: 45%; }
        }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <span class="brand-badge">GODOT 4</span>
            <span class="brand-title">Graphify GDScript Architecture Graph</span>
        </div>
        <div class="token-savings-badge">
            <span class="stat-pill">Project Raw Tokens: <strong>~__RAW_TOKENS__</strong></span>
            <span>&rarr;</span>
            <span class="stat-pill">Target Context: <strong>~__QUERY_TOKENS__</strong></span>
            <span class="stat-pill">Token Reduction: <strong>__SAVED_PCT__% SAVED</strong></span>
        </div>
    </header>

    <div class="main-container">
        <div id="network"></div>
        <div id="status" class="status">Loading graph&hellip;</div>

        <div class="sidebar">
            <h3 style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-secondary);">Controls &amp; Filters</h3>
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
                __COMMUNITY_ITEMS__
            </div>
        </div>

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
        const nodesData = __NODES_JSON__;
        const edgesData = __EDGES_JSON__;
        const VIS_URLS = __VIS_URLS_JSON__;
        const VIS_SRI = __VIS_SRI_JSON__;

        const statusBox = document.getElementById('status');
        function setStatus(text, isError) {
            statusBox.textContent = text;
            statusBox.classList.toggle('error', !!isError);
            statusBox.style.display = text ? 'block' : 'none';
        }

        function escapeHtml(value) {
            return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
        }

        // Load vis-network from the first CDN that answers; say so plainly if none does.
        function loadVis(index) {
            if (index >= VIS_URLS.length) {
                setStatus('Could not load the graph library (vis-network) from unpkg.com or cdn.jsdelivr.net. ' +
                    'graph.html needs internet access to draw the graph; graph.json and GRAPH_REPORT.md ' +
                    'next to this file hold the same data.', true);
                return;
            }
            const script = document.createElement('script');
            script.src = VIS_URLS[index];
            script.integrity = VIS_SRI;
            script.crossOrigin = 'anonymous';
            script.onload = () => (typeof vis !== 'undefined' ? initGraph() : loadVis(index + 1));
            script.onerror = () => loadVis(index + 1);
            document.head.appendChild(script);
        }

        function initGraph() {
            if (!nodesData.length) {
                setStatus('The graph is empty: no Godot files were found when it was built.', true);
                return;
            }
            const labelById = new Map(nodesData.map(n => [n.id, n.label]));

            const nodes = new vis.DataSet(nodesData.map(n => ({
                id: n.id,
                label: n.label,
                color: { background: n.color, border: '#ffffff', highlight: { background: '#ffffff', border: n.color } },
                shape: n.kind === 'autoload_singleton' ? 'hexagon' : (n.kind === 'scene' ? 'box' : 'dot'),
                size: Math.max(14, Math.min(32, 14 + n.degree * 2)),
                font: { color: '#f8fafc', size: 12 },
                data: n
            })));

            const edges = new vis.DataSet(edgesData.map(e => ({
                from: e.source,
                to: e.target,
                label: e.relation,
                arrows: 'to',
                color: { color: '#475569', highlight: '#38bdf8' },
                font: { color: '#94a3b8', size: 9, align: 'middle', strokeWidth: 0 },
                smooth: { type: 'continuous' }
            })));

            const container = document.getElementById('network');
            const options = {
                nodes: { borderWidth: 1 },
                edges: { arrows: { to: { enabled: true, scaleFactor: 0.7 } } },
                physics: {
                    stabilization: { enabled: true, iterations: 400, updateInterval: 25 },
                    barnesHut: { gravitationalConstant: -3000, springLength: 95 }
                },
                interaction: { hover: true, tooltipDelay: 100 }
            };

            setStatus('Laying out ' + nodesData.length + ' nodes…');
            const network = new vis.Network(container, { nodes: nodes, edges: edges }, options);
            window.network = network;

            network.on('stabilizationProgress', p => {
                setStatus('Laying out ' + nodesData.length + ' nodes… ' + Math.round(100 * p.iterations / p.total) + '%');
            });
            network.once('stabilizationIterationsDone', () => {
                // Freeze the layout once it settles: keeps large graphs from burning CPU.
                network.setOptions({ physics: { enabled: false } });
                network.fit();
                setStatus('');
            });

            // Click inspector
            network.on('click', function(params) {
                const inspector = document.getElementById('inspector');
                if (params.nodes.length === 0) {
                    inspector.style.display = 'none';
                    return;
                }
                const nodeId = params.nodes[0];
                const nodeItem = nodesData.find(n => n.id === nodeId);
                if (!nodeItem) return;
                document.getElementById('inspectorTitle').textContent = nodeItem.label;
                document.getElementById('inspectorMeta').innerHTML =
                    '<strong>Kind:</strong> ' + escapeHtml(nodeItem.kind) + '<br>' +
                    '<strong>Subsystem:</strong> ' + escapeHtml(nodeItem.community_name) + '<br>' +
                    '<strong>Source:</strong> ' + escapeHtml(nodeItem.source_file) + ' (' + escapeHtml(nodeItem.source_location) + ')<br>' +
                    '<strong>Total Connections:</strong> ' + nodeItem.degree;

                const connected = edgesData.filter(e => e.source === nodeId || e.target === nodeId);
                document.getElementById('inspectorEdges').innerHTML = connected.map(e => {
                    const outgoing = e.source === nodeId;
                    const other = labelById.get(outgoing ? e.target : e.source) || (outgoing ? e.target : e.source);
                    return '<li style="padding: 2px 0;">' + (outgoing ? '&rarr;' : '&larr;') +
                        ' <strong>' + escapeHtml(e.relation) + '</strong> ' + escapeHtml(other) + '</li>';
                }).join('');
                inspector.style.display = 'block';
            });

            // Search filter (one batched update instead of a redraw per node)
            document.getElementById('searchInput').addEventListener('input', function(e) {
                const q = e.target.value.toLowerCase().trim();
                nodes.update(nodes.get().map(n => ({
                    id: n.id,
                    hidden: !!q && !(n.label.toLowerCase().includes(q) || n.data.kind.toLowerCase().includes(q))
                })));
            });
        }

        loadVis(0);
    </script>
</body>
</html>"""
