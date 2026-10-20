from pathlib import Path
import pytest
from graphify_gdscript.graph_builder import GodotGraphBuilder
from graphify_gdscript.token_optimizer import TokenReductionEngine


def test_token_reduction_query():
    demo_path = Path(__file__).parent.parent / "examples" / "demo_godot_project"
    builder = GodotGraphBuilder(demo_path)
    G = builder.build()
    stats = builder.to_dict()["stats"]

    engine = TokenReductionEngine(G, stats["estimated_raw_tokens"])
    res = engine.query("player health damage", token_budget=1000)

    assert "context" in res
    assert res["actual_tokens"] > 0
    assert res["actual_tokens"] <= 1200  # Within budget allowance
    # The demo is only ~900 raw tokens, so savings are modest; large projects see far more.
    assert res["reduction_percentage"] > 0.0
    assert res["tokens_saved"] > 0
    assert len(res["subgraph_nodes_count"]) if isinstance(res["subgraph_nodes_count"], list) else res["subgraph_nodes_count"] > 0
