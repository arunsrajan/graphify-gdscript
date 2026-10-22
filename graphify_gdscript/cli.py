"""CLI Interface for graphify-gdscript.

Usage:
    graphify-gdscript scan [path]                # Build full Godot knowledge graph and HTML viz
    graphify-gdscript query "<question>"         # GraphRAG search capped at token budget
    graphify-gdscript trace "<signal>"           # Where a signal is declared, emitted, connected
    graphify-gdscript path "<A>" "<B>"           # Shortest relation chain between two symbols
    graphify-gdscript explain "<symbol>"         # One symbol and everything wired to it
    graphify-gdscript token-report [path]        # Audit token reduction & cost savings
    graphify-gdscript mcp [path]                 # Start MCP stdio server for AI IDEs
    graphify-gdscript install [--platform P]     # Install the skill into Claude Code / Codex / Antigravity
    graphify-gdscript claude|codex|antigravity install|uninstall [--project] [--mcp]
    graphify-gdscript uninstall [--platform P]   # Remove what install wrote
    graphify-gdscript install-plugin [path]      # Copy Godot editor addon to project addons/
    graphify-gdscript patch-graphifyy            # Hook into upstream graphifyy package

Project paths are optional: commands walk up from the current directory to project.godot.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from graphify_gdscript.project import resolve_project_root

# Heavy modules (networkx, tree-sitter) are imported inside the commands that need them,
# so installer commands and the Claude Code hook start instantly.


def _build_graph(project_path: Path):
    from graphify_gdscript.graph_builder import GodotGraphBuilder
    builder = GodotGraphBuilder(project_path)
    return builder, builder.build()


def cmd_scan(args: argparse.Namespace) -> int:
    from graphify_gdscript.cluster import detect_communities, label_communities
    from graphify_gdscript.god_nodes import find_god_nodes
    from graphify_gdscript.token_optimizer import TokenReductionEngine
    from graphify_gdscript.visualizer import generate_html_visualization

    project_path = resolve_project_root(args.path)
    print(f"\nScanning Godot project at: {project_path}")

    builder, G = _build_graph(project_path)

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
    from graphify_gdscript.token_optimizer import TokenReductionEngine

    project_path = resolve_project_root(args.path)
    builder, G = _build_graph(project_path)

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
    from graphify_gdscript.token_optimizer import TokenReductionEngine

    project_path = resolve_project_root(args.path)
    builder, G = _build_graph(project_path)
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
    server = GodotMCPServer(resolve_project_root(args.path))
    server.run_stdio()
    return 0


def _focused_query(args: argparse.Namespace, render) -> int:
    project_path = resolve_project_root(args.path)
    _, G = _build_graph(project_path)
    if G.number_of_nodes() == 0:
        print(f"No Godot project files found in {project_path}.")
        return 1
    print(render(G, project_path))
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    from graphify_gdscript.graph_queries import trace_signal
    return _focused_query(args, lambda G, root: trace_signal(G, args.signal, root))


def cmd_path(args: argparse.Namespace) -> int:
    from graphify_gdscript.graph_queries import shortest_path
    return _focused_query(args, lambda G, root: shortest_path(G, args.source, args.target, root))


def cmd_explain(args: argparse.Namespace) -> int:
    from graphify_gdscript.graph_queries import explain_node
    return _focused_query(args, lambda G, root: explain_node(G, args.symbol, root))


def _install_target(args: argparse.Namespace) -> Path:
    project_dir = resolve_project_root(args.path)
    if not (project_dir / "project.godot").exists():
        print(f"note: no project.godot in {project_dir}; writing the project files there anyway.")
    return project_dir


def cmd_install(args: argparse.Namespace) -> int:
    from graphify_gdscript.installer import install
    return install(args.platform, _install_target(args), project=args.project, mcp=args.mcp)


def cmd_uninstall(args: argparse.Namespace) -> int:
    from graphify_gdscript.installer import uninstall
    return uninstall(args.platform, resolve_project_root(args.path), project=args.project)


def cmd_platform(args: argparse.Namespace) -> int:
    """`graphify-gdscript <claude|codex|antigravity> <install|uninstall>`."""
    from graphify_gdscript.installer import install, uninstall
    if args.action == "install":
        return install(args.command, _install_target(args), project=args.project, mcp=args.mcp)
    return uninstall(args.command, resolve_project_root(args.path), project=args.project)


def godot_addon_source(package_dir: Path = Path(__file__).resolve().parent) -> Path | None:
    """The Godot editor addon to install: the copy shipped in the wheel (godot_addon/),
    else addons/graphify_gdscript/ in the source checkout (editable installs)."""
    for candidate in (package_dir / "godot_addon", package_dir.parent / "addons" / "graphify_gdscript"):
        if (candidate / "plugin.cfg").is_file():
            return candidate
    return None


def cmd_install_plugin(args: argparse.Namespace) -> int:
    dest_project = Path(args.path).resolve()
    if not (dest_project / "project.godot").exists():
        print(f"Warning: {dest_project} does not have project.godot, but proceeding with installation.")

    source_addon = godot_addon_source()
    if source_addon is None:
        print("Error: the Godot addon is missing from this graphify-gdscript installation; reinstall it.")
        return 1

    target_addon = dest_project / "addons" / "graphify_gdscript"
    target_addon.parent.mkdir(parents=True, exist_ok=True)
    if target_addon.exists():
        shutil.rmtree(target_addon)

    shutil.copytree(source_addon, target_addon, ignore=shutil.ignore_patterns(".*", "*.import", "__pycache__"))
    print(f"Successfully installed Godot Editor Plugin to: {target_addon}")
    print("To enable the plugin: Open Godot -> Project -> Project Settings -> Plugins -> Enable 'Graphify GDScript'")
    return 0


def cmd_patch_graphifyy(args: argparse.Namespace) -> int:
    from graphify_gdscript.bridge_graphify import patch_graphifyy
    ok = patch_graphifyy()
    if ok:
        print("Successfully patched graphifyy to support GDScript (.gd) and Godot Scenes (.tscn)!")
        return 0
    else:
        print("Could not patch graphifyy (is graphifyy installed in Python environment?)")
        return 1


PROJECT_HELP = "Godot project path (default: nearest folder with project.godot)"
PLATFORM_NAMES = ("claude", "codex", "antigravity")


def _add_install_flags(p: argparse.ArgumentParser, uninstall: bool = False) -> None:
    p.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)
    p.add_argument("--project", action="store_true",
                   help="project scope: skill inside the project, bare commands safe to commit")
    if not uninstall:
        p.add_argument("--mcp", action="store_true", help="also register the graphify-gdscript MCP server")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphify-gdscript",
        description="Graphify GDScript: Knowledge graph generator & LLM token optimizer for Godot",
    )
    subparsers = parser.add_subparsers(dest="command")

    p_scan = subparsers.add_parser("scan", help="Scan Godot project and generate knowledge graph")
    p_scan.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)

    p_query = subparsers.add_parser("query", help="Query knowledge graph within a token budget")
    p_query.add_argument("question", help="Question or concept to search")
    p_query.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)
    p_query.add_argument("--budget", type=int, default=1500, help="Max tokens allowed for context")
    p_query.add_argument("--mode", choices=["bfs", "dfs"], default="bfs", help="Search traversal mode")
    p_query.add_argument("--depth", type=int, default=2, help="Neighborhood depth")

    p_trace = subparsers.add_parser("trace", help="Trace where a signal is declared, emitted and connected")
    p_trace.add_argument("signal", help="Signal name, e.g. health_changed")
    p_trace.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)

    p_path = subparsers.add_parser("path", help="Shortest chain of relations between two symbols")
    p_path.add_argument("source", help="First symbol, e.g. Player")
    p_path.add_argument("target", help="Second symbol, e.g. GameManager.trigger_game_over")
    p_path.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)

    p_explain = subparsers.add_parser("explain", help="Show one symbol and everything wired to it")
    p_explain.add_argument("symbol", help="Symbol name, e.g. take_damage")
    p_explain.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)

    p_report = subparsers.add_parser("token-report", help="Generate token savings audit report")
    p_report.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)

    p_mcp = subparsers.add_parser("mcp", help="Start MCP stdio server")
    p_mcp.add_argument("path", nargs="?", default=None, help=PROJECT_HELP)

    p_install = subparsers.add_parser(
        "install", help="Install the skill and always-on rules into an AI coding assistant")
    p_install.add_argument("--platform", choices=[*PLATFORM_NAMES, "all"], default="claude",
                           help="assistant to install into (default: claude)")
    _add_install_flags(p_install)

    p_uninstall = subparsers.add_parser("uninstall", help="Remove what install wrote")
    p_uninstall.add_argument("--platform", choices=[*PLATFORM_NAMES, "all"], default="all",
                             help="assistant to uninstall from (default: all)")
    _add_install_flags(p_uninstall, uninstall=True)

    displays = {"claude": "Claude Code", "codex": "OpenAI Codex", "antigravity": "Google Antigravity"}
    for name in PLATFORM_NAMES:
        p = subparsers.add_parser(name, help=f"Install or uninstall graphify-gdscript for {displays[name]}")
        p.add_argument("action", choices=["install", "uninstall"])
        _add_install_flags(p)

    p_guard = subparsers.add_parser("guard", help="PreToolUse hook used by Claude Code (reads JSON on stdin)")
    p_guard.add_argument("kind", choices=["search", "read"])

    p_inst = subparsers.add_parser("install-plugin", help="Install Godot Editor Plugin to a project")
    p_inst.add_argument("path", nargs="?", default=".", help="Target Godot project root directory")

    subparsers.add_parser("patch-graphifyy", help="Hook into upstream graphifyy installation")
    return parser


COMMANDS = {
    "scan": cmd_scan,
    "query": cmd_query,
    "trace": cmd_trace,
    "path": cmd_path,
    "explain": cmd_explain,
    "token-report": cmd_token_report,
    "mcp": cmd_mcp,
    "install": cmd_install,
    "uninstall": cmd_uninstall,
    "claude": cmd_platform,
    "codex": cmd_platform,
    "antigravity": cmd_platform,
    "install-plugin": cmd_install_plugin,
    "patch-graphifyy": cmd_patch_graphifyy,
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["guard"]:
        # Hot path: runs before every Claude Code Read/Grep call. Never fails the tool call.
        from graphify_gdscript.guard import run
        run(argv[1] if len(argv) > 1 else "")
        sys.exit(0)

    if argv[:1] != ["mcp"] and hasattr(sys.stdout, "reconfigure"):
        # Graph labels can hold characters a legacy Windows console codepage cannot print.
        sys.stdout.reconfigure(errors="backslashreplace")

    args = build_parser().parse_args(argv)
    if not args.command:
        # Default behavior: scan the current project
        args.command = "scan"
        args.path = None
    sys.exit(COMMANDS[args.command](args))


if __name__ == "__main__":
    main()
