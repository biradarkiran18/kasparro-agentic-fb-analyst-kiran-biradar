from src.agents.planner import plan

def test_planner_structure():
    out = plan("test")
    assert "steps" in out
    assert len(out["steps"]) == 7
