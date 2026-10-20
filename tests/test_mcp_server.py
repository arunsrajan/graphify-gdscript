import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from graphify_gdscript.mcp_server import GodotMCPServer

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo_godot_project"


@pytest.fixture
def server():
    return GodotMCPServer(DEMO)


def _req(req_id, method, params=None):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def test_every_request_gets_a_response(server):
    # Clients block forever on a request that never gets a reply.
    for method in ("ping", "resources/list", "prompts/list", "some/unknown"):
        resp = server.handle_message(_req(7, method))
        assert resp is not None and resp["id"] == 7
        assert ("result" in resp) != ("error" in resp)


def test_notifications_get_no_response(server):
    assert server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.handle_message({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}}) is None


def test_initialize_negotiates_protocol_version(server):
    resp = server.handle_message(_req(1, "initialize", {"protocolVersion": "2024-11-05"}))
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    resp = server.handle_message(_req(2, "initialize", {"protocolVersion": "1999-01-01"}))
    assert resp["result"]["protocolVersion"] == "2025-06-18"


def test_tool_errors_are_reported_as_tool_results(server):
    resp = server.handle_message(_req(3, "tools/call", {"name": "does_not_exist"}))
    assert resp["result"]["isError"] is True
    resp = server.handle_message(_req(4, "tools/call", {"name": "gdscript_trace_signal", "arguments": None}))
    assert resp["result"]["isError"] is True


def test_autoloads_are_not_clobbered_by_references(server):
    resp = server.handle_message(_req(5, "tools/call", {"name": "gdscript_get_autoloads", "arguments": {}}))
    text = resp["result"]["content"][0]["text"]
    assert "GameManager" in text and "EventBus" in text


def test_trace_signal_matches_signal_names_only(server):
    resp = server.handle_message(_req(6, "tools/call", {"name": "gdscript_trace_signal", "arguments": {"signal_name": "health_changed"}}))
    text = resp["result"]["content"][0]["text"]
    assert "health_changed" in text
    assert "player_died" not in text


def test_stdio_session_does_not_hang():
    proc = subprocess.Popen(
        [sys.executable, "-m", "graphify_gdscript.mcp_server", str(DEMO)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    lines: "queue.Queue[bytes]" = queue.Queue()
    threading.Thread(target=lambda: [lines.put(l) for l in proc.stdout], daemon=True).start()

    def send(msg):
        proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        proc.stdin.flush()

    try:
        send(_req(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}}))
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(_req(2, "ping"))
        send(_req(3, "tools/list"))
        send(_req(4, "tools/call", {"name": "gdscript_query_graph", "arguments": {"question": "player damage"}}))
        ids = []
        for _ in range(4):
            raw = lines.get(timeout=30)
            assert not raw.endswith(b"\r\n")
            ids.append(json.loads(raw)["id"])
        assert ids == [1, 2, 3, 4]
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)
