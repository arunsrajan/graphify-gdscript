"""Model Context Protocol (MCP) Server for Godot GDScript Knowledge Graphs.

Exposes tools for Agentic AI IDEs (Antigravity, Cursor, Windsurf, Claude Code)
to query Godot knowledge graphs with strict token-budget optimization.
"""
from __future__ import annotations


import io
import json
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from graphify_gdscript.graph_builder import GodotGraphBuilder
from graphify_gdscript.graph_queries import explain_node, shortest_path, trace_signal
from graphify_gdscript.god_nodes import find_god_nodes
from graphify_gdscript.project import resolve_project_root
from graphify_gdscript.token_optimizer import TokenReductionEngine

SERVER_VERSION = "1.0.0"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "gdscript_query_graph",
        "description": "Query Godot knowledge graph with BFS/DFS within a token budget to reduce LLM prompt tokens by 90-99%.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question or keyword to search in Godot project"},
                "token_budget": {"type": "integer", "description": "Token budget cap (default 1500)", "default": 1500},
                "mode": {"type": "string", "enum": ["bfs", "dfs"], "default": "bfs"},
                "depth": {"type": "integer", "description": "Traversal depth (1-4)", "default": 2},
            },
            "required": ["question"],
        },
    },
    {
        "name": "gdscript_token_reduction_report",
        "description": "Calculate LLM token and cost savings for this Godot project.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "gdscript_trace_signal",
        "description": "Trace signal emissions, connections, and recipient callbacks across scenes and scripts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "signal_name": {"type": "string", "description": "Name of the Godot signal"}
            },
            "required": ["signal_name"],
        },
    },
    {
        "name": "gdscript_get_autoloads",
        "description": "List all global Autoload singletons and their implementation scripts/scenes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "gdscript_get_god_nodes",
        "description": "Identify architectural God Nodes and critical bottlenecks in the project.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "gdscript_shortest_path",
        "description": "Shortest chain of relations (calls, signals, scene wiring, autoloads) linking two symbols.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "First symbol, e.g. Player"},
                "target": {"type": "string", "description": "Second symbol, e.g. GameManager.trigger_game_over"},
            },
            "required": ["source", "target"],
        },
    },
    {
        "name": "gdscript_explain",
        "description": "One symbol (class, function, signal, scene node, autoload) with its location and every relation in and out.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name, e.g. take_damage"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "gdscript_rebuild_graph",
        "description": "Rebuild the knowledge graph after project files changed on disk.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class ToolError(Exception):
    """Error reported back to the client as a tool result with isError set."""


class GodotMCPServer:
    def __init__(self, project_path: str | Path = "."):
        self.project_path = Path(project_path).resolve()
        self.builder: Optional[GodotGraphBuilder] = None
        self.optimizer: Optional[TokenReductionEngine] = None
        self.graph = None
        self._build_lock = threading.Lock()
        self._out = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else sys.stdout
        self._out_lock = threading.Lock()

    def ensure_graph(self, force: bool = False) -> None:
        """Build the project knowledge graph (once, unless forced)."""
        with self._build_lock:
            if self.graph is not None and not force:
                return
            if not self.project_path.is_dir():
                raise ToolError(f"Project path does not exist or is not a directory: {self.project_path}")
            builder = GodotGraphBuilder(self.project_path)
            graph = builder.build()
            stats = builder.to_dict()["stats"]
            self.optimizer = TokenReductionEngine(graph, stats["estimated_raw_tokens"])
            self.builder = builder
            self.graph = graph

    def prebuild_in_background(self) -> None:
        """Warm the graph off the protocol thread so the first tool call returns fast."""
        def _warm() -> None:
            try:
                self.ensure_graph()
            except Exception as e:  # reported again on the first tool call
                print(f"[graphify-gdscript] graph prebuild failed: {e}", file=sys.stderr, flush=True)

        threading.Thread(target=_warm, name="graph-prebuild", daemon=True).start()

    def handle_tool_call(self, name: str, args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Dispatch tool calls."""
        args = args or {}
        if name not in {t["name"] for t in TOOLS}:
            raise ToolError(f"Unknown tool: {name}")

        if name == "gdscript_rebuild_graph":
            self.ensure_graph(force=True)
            stats = self.builder.to_dict()["stats"]
            return {"content": [{"type": "text", "text": f"Graph rebuilt: {stats['total_nodes']} nodes, {stats['total_edges']} edges, {stats['total_files']} files."}]}

        self.ensure_graph()

        if name == "gdscript_query_graph":
            question = str(args.get("question", "")).strip()
            if not question:
                raise ToolError("'question' is required")
            try:
                token_budget = max(100, int(args.get("token_budget", 1500)))
                depth = min(max(int(args.get("depth", 2)), 1), 4)
            except (TypeError, ValueError):
                raise ToolError("'token_budget' and 'depth' must be integers")
            mode = args.get("mode", "bfs")

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
            signal_name = str(args.get("signal_name", "")).strip()
            if not signal_name:
                raise ToolError("'signal_name' is required")
            text = trace_signal(self.graph, signal_name, self.project_path)
            return {"content": [{"type": "text", "text": text}]}

        elif name == "gdscript_shortest_path":
            source = str(args.get("source", "")).strip()
            target = str(args.get("target", "")).strip()
            if not source or not target:
                raise ToolError("'source' and 'target' are required")
            text = shortest_path(self.graph, source, target, self.project_path)
            return {"content": [{"type": "text", "text": text}]}

        elif name == "gdscript_explain":
            symbol = str(args.get("symbol", "")).strip()
            if not symbol:
                raise ToolError("'symbol' is required")
            text = explain_node(self.graph, symbol, self.project_path)
            return {"content": [{"type": "text", "text": text}]}

        elif name == "gdscript_get_autoloads":
            autoload_nodes = [
                d for nid, d in self.graph.nodes.items() if d.get("kind") == "autoload_singleton"
            ]
            lines = ["## Global Autoload Singletons in Project:\n"]
            for a in autoload_nodes:
                lines.append(f"- **{a.get('singleton_name') or a.get('label')}**: `{a.get('res_path')}`")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        elif name == "gdscript_get_god_nodes":
            gods = find_god_nodes(self.graph, top_k=5)
            lines = ["## Top Architectural God Nodes in Project:\n"]
            for g in gods:
                lines.append(f"- **{g['label']}** ({g['kind']}): Degree {g['degree']} (In: {g['in_degree']}, Out: {g['out_degree']})\n  *Role:* {g['architectural_role']}")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        raise ToolError(f"Unknown tool: {name}")

    # ------------------------------------------------------------------
    # JSON-RPC / MCP stdio transport
    # ------------------------------------------------------------------

    def _send(self, msg: Dict[str, Any]) -> None:
        data = json.dumps(msg, ensure_ascii=False) + "\n"
        with self._out_lock:
            if not isinstance(self._out, io.TextIOBase):
                data = data.encode("utf-8")
            self._out.write(data)
            self._out.flush()

    def _send_error(self, req_id: Any, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

    def handle_message(self, msg: Any) -> Optional[Dict[str, Any]]:
        """Handle one decoded JSON-RPC message; returns the response or None for notifications."""
        if not isinstance(msg, dict):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}

        method = msg.get("method")
        req_id = msg.get("id")
        is_notification = "id" not in msg

        if method is None:
            # A response to a server->client request (we never send any) - ignore.
            return None
        if is_notification:
            # notifications/initialized, notifications/cancelled, ... need no reply.
            return None

        def ok(result: Dict[str, Any]) -> Dict[str, Any]:
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        if method == "initialize":
            params = msg.get("params") or {}
            requested = params.get("protocolVersion")
            version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
            self.prebuild_in_background()
            return ok({
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "graphify-gdscript", "version": SERVER_VERSION},
            })
        if method == "ping":
            return ok({})
        if method == "tools/list":
            return ok({"tools": TOOLS})
        if method == "tools/call":
            params = msg.get("params") or {}
            try:
                return ok(self.handle_tool_call(params.get("name", ""), params.get("arguments")))
            except Exception as e:
                text = str(e) if isinstance(e, ToolError) else f"{type(e).__name__}: {e}"
                return ok({"content": [{"type": "text", "text": f"Error: {text}"}], "isError": True})
        if method in ("resources/list", "resources/templates/list", "prompts/list"):
            key = {"resources/list": "resources", "resources/templates/list": "resourceTemplates", "prompts/list": "prompts"}[method]
            return ok({key: []})

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    def run_stdio(self) -> None:
        """Run MCP stdio protocol loop (newline-delimited JSON-RPC over UTF-8)."""
        stdin = sys.stdin.buffer if hasattr(sys.stdin, "buffer") else sys.stdin
        # Write raw UTF-8 bytes: no locale codec and no CRLF translation on Windows.
        self._out = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else sys.stdout
        # Anything else that prints must not corrupt the protocol stream.
        sys.stdout = sys.stderr

        while True:
            raw = stdin.readline()
            if not raw:
                break  # client closed stdin
            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
            line = line.strip().lstrip("\ufeff")
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError as e:
                self._send_error(None, -32700, f"Parse error: {e}")
                continue
            try:
                resp = self.handle_message(msg)
            except Exception as e:
                req_id = msg.get("id") if isinstance(msg, dict) else None
                resp = None if isinstance(msg, dict) and "id" not in msg else {
                    "jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}
            if resp is not None:
                self._send(resp)

def main():
    server = GodotMCPServer(resolve_project_root(sys.argv[1] if len(sys.argv) > 1 else None))
    server.run_stdio()


if __name__ == "__main__":
    main()
