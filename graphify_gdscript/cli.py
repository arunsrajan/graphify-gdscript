"""CLI Interface for graphify-gdscript.

Usage:
    graphify-gdscript scan [path]                # Build full Godot knowledge graph and HTML viz
    graphify-gdscript query "<question>"         # GraphRAG search capped at token budget
    graphify-gdscript token-report [path]        # Audit token reduction & cost savings
    graphify-gdscript mcp [path]                 # Start MCP stdio server for AI IDEs
    graphify-gdscript install-plugin [path]      # Copy Godot editor addon to project addons/
    graphify-gdscript patch-graphifyy            # Hook into upstream graphifyy package
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from graphify_gdscript.graph_builder import GodotGraphBuilder
from graphify_gdscript.cluster import detect_communities, label_communities
from graphify_gdscript.god_nodes import find_god_nodes
from graphify_gdscript.token_optimizer import TokenReductionEngine
from graphify_gdscript.visualizer import generate_html_visualization
from graphify_gdscript.bridge_graphify import patch_graphifyy


def cmd_scan(args: argparse.Namespace) -> int:
    project_path = Path(args.path).resolve()
    print(f"\nScanning Godot project at: {project_path}")
    
    builder = GodotGraphBuilder(project_path)
    G = builder.build()
    
    if G.number_of_nodes() == 0:
        print("No Godot (.gd, .tscn, project.godot) files found in path.")
        return 1

    communities = detect_communities(G)
    community_labels = label_communities(G, communities)
    gods = find_god_nodes(G, top_k=5)
    
    stats = builder.to_dict()["stats"]
    optimizer = TokenReductionEngine(G, stats["estimated_raw_tokens"])
    sample_query = optimizer.query("player movement and combat signals", token_budget=1500)

    out_dir = project_path / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export graph.json
    graph_json_path = out_dir / "graph.json"
    export_dict = builder.to_dict()
    export_dict["communities"] = {str(k): v for k, v in communities.items()}
    export_dict["community_labels"] = {str(k): v for k, v in community_labels.items()}
    export_dict["god_nodes"] = gods
    graph_json_path.write_text(json.dumps(export_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Export graph.html
    html_path = out_dir / "graph.html"
    generate_html_visualization(G, communities, community_labels, stats, html_path)

    # 3. Export GRAPH_REPORT.md
    report_path = out_dir / "GRAPH_REPORT.md"
    report_lines = [
        f"# Godot GDScript Architecture & Knowledge Graph Report",
        f"\n**Project Path:** `{project_path}`",
        f"- **Total Nodes:** {G.number_of_nodes()}",
        f"- **Total Edges:** {G.number_of_edges()}",
        f"- **Subsystem Communities:** {len(communities)}",
        f"\n## ⚡ Token Reduction Benchmark",
        f"- **Naive Whole-Repo Context:** ~{stats['estimated_raw_tokens']:,} tokens",
        f"- **Graphify-GDScript Query Context:** ~{sample_query['actual_tokens']:,} tokens",
        f"- **Token Consumption Reduction:** **{sample_query['reduction_percentage']}% SAVED**",
        f"- **Estimated Cost Saved:** ~${sample_query['estimated_cost_saved_usd']} per query",
        f"\n## 🏛️ Top God Nodes (Architectural Hubs)",
    ]
    for g in gods:
        report_lines.append(f"- **{g['label']}** ({g['kind']}) — Degree: {g['degree']} (In: {g['in_degree']}, Out: {g['out_degree']})")
        report_lines.append(f"  *{g['architectural_role']}*")

    report_lines.append(f"\n## 🧩 Subsystem Communities")
    for cid, cname in community_labels.items():
        report_lines.append(f"- **{cname}:** {len(communities[cid])} nodes")

    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"Graphify GDScript Complete!")
    print(f"  Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()} | Subsystems: {len(communities)}")
    print(f"  Token Savings: {sample_query['reduction_percentage']}% REDUCTION (~{stats['estimated_raw_tokens']:,} raw -> ~{sample_query['actual_tokens']:,} graph)")
    print("=" * 60)
    print(f"Outputs written to: {out_dir}")
    print(f"  - graph.html        (interactive visualization)")
    print(f"  - graph.json        (GraphRAG JSON)")
    print(f"  - GRAPH_REPORT.md   (architecture audit)")
    print("=" * 60 + "\n")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    project_path = Path(args.path).resolve()
    builder = GodotGraphBuilder(project_path)
    G = builder.build()
    
    if G.number_of_nodes() == 0:
        print("No Godot project files found in path.")
        return 1

    stats = builder.to_dict()["stats"]
    optimizer = TokenReductionEngine(G, stats["estimated_raw_tokens"])
    res = optimizer.query(args.question, token_budget=args.budget, mode=args.mode, depth=args.depth)

    print("\n" + res["context"] + "\n")
    print("-" * 60)
    print(f"TOKEN CONSUMPTION AUDIT:")
    print(f"  Raw Project Tokens: ~{res['raw_project_tokens']:,}")
    print(f"  Pruned Context:     ~{res['actual_tokens']:,}")
    print(f"  Token Reduction:    {res['reduction_percentage']}% SAVED (~${res['estimated_cost_saved_usd']} saved per query)")
    print("-" * 60 + "\n")
    return 0


def cmd_token_report(args: argparse.Namespace) -> int:
    project_path = Path(args.path).resolve()
    builder = GodotGraphBuilder(project_path)
    G = builder.build()
    stats = builder.to_dict()["stats"]
    optimizer = TokenReductionEngine(G, stats["estimated_raw_tokens"])
    sample = optimizer.query("overview of core systems", token_budget=1500)

    print("\n" + "=" * 60)
    print("   GODOT GDSCRIPT TOKEN REDUCTION AUDIT REPORT")
    print("=" * 60)
    print(f"Project: {project_path}")
    print(f"Extracted Nodes: {stats['total_nodes']} | Edges: {stats['total_edges']}")
    print(f"\n1. NAIVE LLM WHOLE-PROJECT DUMP:")
    print(f"   Context Size:       ~{stats['estimated_raw_tokens']:,} tokens")
    print(f"   Cost per 100 queries: ${(stats['estimated_raw_tokens'] * 100 / 1e6) * 3:.2f}")
    print(f"\n2. GRAPHIFY-GDSCRIPT PRUNED CONTEXT:")
    print(f"   Context Size:       ~{sample['actual_tokens']:,} tokens")
    print(f"   Cost per 100 queries: ${(sample['actual_tokens'] * 100 / 1e6) * 3:.2f}")
    print(f"\n3. TOTAL REDUCTION:")
    print(f"   Tokens Saved:       ~{sample['tokens_saved']:,} tokens ({sample['reduction_percentage']}%)")
    print(f"   Money Saved / 100q:  ${((stats['estimated_raw_tokens'] - sample['actual_tokens']) * 100 / 1e6) * 3:.2f}")
    print("=" * 60 + "\n")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from graphify_gdscript.mcp_server import GodotMCPServer
    server = GodotMCPServer(args.path)
    server.run_stdio()
    return 0


def cmd_install_plugin(args: argparse.Namespace) -> int:
    dest_project = Path(args.path).resolve()
    if not (dest_project / "project.godot").exists():
        print(f"Warning: {dest_project} does not have project.godot, but proceeding with installation.")

    source_addon = Path(__file__).parent.parent / "addons" / "graphify_gdscript"
    if not source_addon.exists():
        print(f"Error: Could not locate source addon at {source_addon}")
        return 1

    target_addon = dest_project / "addons" / "graphify_gdscript"
    target_addon.parent.mkdir(parents=True, exist_ok=True)
    if target_addon.exists():
        shutil.rmtree(target_addon)

    shutil.copytree(source_addon, target_addon)
    print(f"Successfully installed Godot Editor Plugin to: {target_addon}")
    print("To enable the plugin: Open Godot -> Project -> Project Settings -> Plugins -> Enable 'Graphify GDScript'")
    return 0


def cmd_patch_graphifyy(args: argparse.Namespace) -> int:
    ok = patch_graphifyy()
    if ok:
        print("Successfully patched graphifyy to support GDScript (.gd) and Godot Scenes (.tscn)!")
        return 0
    else:
        print("Could not patch graphifyy (is graphifyy installed in Python environment?)")
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog="graphify-gdscript",
        description="Graphify GDScript: Knowledge graph generator & LLM token optimizer for Godot",
    )
    subparsers = parser.add_subparsers(dest="command")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan Godot project and generate knowledge graph")
    p_scan.add_argument("path", nargs="?", default=".", help="Project path (default: current directory)")

    # query
    p_query = subparsers.add_parser("query", help="Query knowledge graph within a token budget")
    p_query.add_argument("question", help="Question or concept to search")
    p_query.add_argument("path", nargs="?", default=".", help="Project path")
    p_query.add_argument("--budget", type=int, default=1500, help="Max tokens allowed for context")
    p_query.add_argument("--mode", choices=["bfs", "dfs"], default="bfs", help="Search traversal mode")
    p_query.add_argument("--depth", type=int, default=2, help="Neighborhood depth")

    # token-report
    p_report = subparsers.add_parser("token-report", help="Generate token savings audit report")
    p_report.add_argument("path", nargs="?", default=".", help="Project path")

    # mcp
    p_mcp = subparsers.add_parser("mcp", help="Start MCP stdio server")
    p_mcp.add_argument("path", nargs="?", default=".", help="Project path")

    # install-plugin
    p_inst = subparsers.add_parser("install-plugin", help="Install Godot Editor Plugin to a project")
    p_inst.add_argument("path", default=".", help="Target Godot project root directory")

    # patch-graphifyy
    subparsers.add_parser("patch-graphifyy", help="Hook into upstream graphifyy installation")

    args = parser.parse_args()
    if not args.command:
        # Default behavior: run scan on current directory
        args.command = "scan"
        args.path = "."

    if args.command == "scan":
        sys.exit(cmd_scan(args))
    elif args.command == "query":
        sys.exit(cmd_query(args))
    elif args.command == "token-report":
        sys.exit(cmd_token_report(args))
    elif args.command == "mcp":
        sys.exit(cmd_mcp(args))
    elif args.command == "install-plugin":
        sys.exit(cmd_install_plugin(args))
    elif args.command == "patch-graphifyy":
        sys.exit(cmd_patch_graphifyy(args))


if __name__ == "__main__":
    main()
