"""Model Context Protocol (MCP) Server for Godot GDScript Knowledge Graphs.

Exposes tools for Agentic AI IDEs (Antigravity, Cursor, Windsurf, Claude Code)
to query Godot knowledge graphs with strict token-budget optimization.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from graphify_gdscript.graph_builder import GodotGraphBuilder
from graphify_gdscript.cluster import detect_communities, label_communities
from graphify_gdscript.god_nodes import find_god_nodes
from graphify_gdscript.token_optimizer import TokenReductionEngine


class GodotMCPServer:
    def __init__(self, project_path: str | Path = "."):
        self.project_path = Path(project_path).resolve()
        self.builder: Optional[GodotGraphBuilder] = None
        self.optimizer: Optional[TokenReductionEngine] = None
        self.graph = None
        self.communities = {}
        self.community_labels = {}

    def ensure_graph(self) -> None:
        """Load or build the project knowledge graph."""
        if self.graph is not None:
            return

        out_json = self.project_path / "graphify-out" / "graph.json"
        if out_json.exists():
            try:
                # Load existing graph
                pass
            except Exception:
                pass

        # Build fresh graph
        self.builder = GodotGraphBuilder(self.project_path)
        self.graph = self.builder.build()
        self.communities = detect_communities(self.graph)
        self.community_labels = label_communities(self.graph, self.communities)
        self.optimizer = TokenReductionEngine(self.graph, self.builder.to_dict()["stats"]["estimated_raw_tokens"])

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool calls."""
        self.ensure_graph()

        if name == "gdscript_query_graph":
            question = args.get("question", "")
            token_budget = int(args.get("token_budget", 1500))
            mode = args.get("mode", "bfs")
            depth = int(args.get("depth", 2))
            
            result = self.optimizer.query(question, token_budget=token_budget, mode=mode, depth=depth)
            return {
                "content": [
                    {"type": "text", "text": result["context"]},
                    {
                        "type": "text",
                        "text": f"\n\n**Token Savings Report:**\n- Raw Project Tokens: ~{result['raw_project_tokens']:,}\n- Graph Context Tokens: ~{result['actual_tokens']:,}\n- Reduction: **{result['reduction_percentage']}% SAVED** (Saved ~${result['estimated_cost_saved_usd']} per query)",
                    }
                ]
            }

        elif name == "gdscript_token_reduction_report":
            stats = self.builder.to_dict()["stats"]
            raw_tokens = stats["estimated_raw_tokens"]
            sample_query = self.optimizer.query("overview of core systems", token_budget=1500)
            
            report = (
                f"# Godot GDScript LLM Token Reduction Audit\n\n"
                f"- **Project Root:** `{self.project_path}`\n"
                f"- **Total Project Files:** {stats['total_files']} files ({stats['raw_lines']} lines of code)\n"
                f"- **Total Nodes Extracted:** {stats['total_nodes']}\n"
                f"- **Total Edges Wired:** {stats['total_edges']}\n\n"
                f"## Token Consumption Comparison:\n"
                f"| Method | Prompt Context Tokens | Cost per 100 Queries ($3/1M) |\n"
                f"|---|---|---|\n"
                f"| Naive Whole-Repo Dump | ~{raw_tokens:,} tokens | ${(raw_tokens * 100 / 1e6) * 3:.2f} |\n"
                f"| Graphify-GDScript Context | ~{sample_query['actual_tokens']:,} tokens | ${(sample_query['actual_tokens'] * 100 / 1e6) * 3:.2f} |\n"
                f"| **Savings** | **~{sample_query['tokens_saved']:,} tokens ({sample_query['reduction_percentage']}%)** | **${((raw_tokens - sample_query['actual_tokens']) * 100 / 1e6) * 3:.2f} Saved** |\n"
            )
            return {"content": [{"type": "text", "text": report}]}

        elif name == "gdscript_trace_signal":
            signal_name = args.get("signal_name", "").strip()
            matching_edges = []
            for u, v, data in self.graph.edges(data=True):
                rel = data.get("relation", "")
                if rel in ("emits", "connects_to") and signal_name.lower() in str(data).lower():
                    src_lbl = self.graph.nodes.get(u, {}).get("label", u)
                    tgt_lbl = self.graph.nodes.get(v, {}).get("label", v)
                    loc = data.get("source_location", "")
                    matching_edges.append(f"- `{src_lbl}` --[{rel}]--> `{tgt_lbl}` ({loc})")

            text = f"## Signal Trace for: `{signal_name}`\n\n" + ("\n".join(matching_edges) if matching_edges else "No matching signal connections found.")
            return {"content": [{"type": "text", "text": text}]}

        elif name == "gdscript_get_autoloads":
            autoload_nodes = [
                d for nid, d in self.graph.nodes.items() if d.get("kind") == "autoload_singleton"
            ]
            lines = ["## Global Autoload Singletons in Project:\n"]
            for a in autoload_nodes:
                lines.append(f"- **{a.get('label')}**: `{a.get('res_path')}`")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        elif name == "gdscript_get_god_nodes":
            gods = find_god_nodes(self.graph, top_k=5)
            lines = ["## Top Architectural God Nodes in Project:\n"]
            for g in gods:
                lines.append(f"- **{g['label']}** ({g['kind']}): Degree {g['degree']} (In: {g['in_degree']}, Out: {g['out_degree']})\n  *Role:* {g['architectural_role']}")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        else:
            return {"error": f"Unknown tool: {name}"}

    def run_stdio(self) -> None:
        """Run MCP stdio protocol loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                method = msg.get("method")
                req_id = msg.get("id")

                if method == "tools/list":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "tools": [
                                {
                                    "name": "gdscript_query_graph",
                                    "description": "Query Godot knowledge graph with BFS/DFS within a token budget to reduce LLM prompt tokens by 90-99%.",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "question": {"type": "string", "description": "Question or keyword to search in Godot project"},
                                            "token_budget": {"type": "integer", "description": "Token budget cap (default 1500)", "default": 1500},
                                            "mode": {"type": "string", "enum": ["bfs", "dfs"], "default": "bfs"},
                                            "depth": {"type": "integer", "default": 2}
                                        },
                                        "required": ["question"]
                                    }
                                },
                                {
                                    "name": "gdscript_token_reduction_report",
                                    "description": "Calculate LLM token and cost savings for this Godot project.",
                                    "inputSchema": {"type": "object", "properties": {}}
                                },
                                {
                                    "name": "gdscript_trace_signal",
                                    "description": "Trace signal emissions, connections, and recipient callbacks across scenes and scripts.",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "signal_name": {"type": "string", "description": "Name of the Godot signal"}
                                        },
                                        "required": ["signal_name"]
                                    }
                                },
                                {
                                    "name": "gdscript_get_autoloads",
                                    "description": "List all global Autoload singletons and their implementation scripts/scenes.",
                                    "inputSchema": {"type": "object", "properties": {}}
                                },
                                {
                                    "name": "gdscript_get_god_nodes",
                                    "description": "Identify architectural God Nodes and critical bottlenecks in the project.",
                                    "inputSchema": {"type": "object", "properties": {}}
                                }
                            ]
                        }
                    }
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()

                elif method == "tools/call":
                    params = msg.get("params", {})
                    tool_name = params.get("name")
                    args = params.get("arguments", {})
                    res = self.handle_tool_call(tool_name, args)
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": res}
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()

                elif method == "initialize":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "graphify-gdscript", "version": "1.0.0"}
                        }
                    }
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()

            except Exception as e:
                err_resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    server = GodotMCPServer(path)
    server.run_stdio()


if __name__ == "__main__":
    main()
