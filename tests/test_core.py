import asyncio

from app.cases import classify
from app.llm import extract_json
from app.personas import AUDIENCES, sample_population
from app.simulate import Run, run_simulation, segment_metrics
from app.llm import Router


def test_population_deterministic_and_connected():
    a = sample_population(300, "all", 7)
    b = sample_population(300, "all", 7)
    assert [p.bio() for p in a] == [p.bio() for p in b]
    assert all(p.neighbors for p in a)
    assert 0.2 < sum(p.urban for p in a) / len(a) < 0.5


def test_audiences_filter():
    assert all(p.urban for p in sample_population(200, "urban_online"))
    assert all(not p.urban for p in sample_population(200, "rural"))
    assert all(18 <= p.age <= 27 for p in sample_population(200, "genz"))
    assert set(AUDIENCES) >= {"all", "urban_online", "genz", "rural", "smb"}


def test_extract_json_handles_think_and_fences():
    assert extract_json('<think>hmm {"x":1}</think>```json\n{"stance": -2}\n```') == {"stance": -2}
    assert extract_json('Sure! {"a": "b {c}"} trailing') == {"a": "b {c}"}
    import pytest
    with pytest.raises(ValueError):
        extract_json('{"a": 1, "b": [1,2')


def test_classify():
    assert classify(0.8, 0.8) == "embraced"
    assert classify(-0.6, 0.6) == "accepted"
    assert classify(-0.9, 0.2) == "rejected"


def test_demo_simulation_end_to_end(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    r = Run(id="t", proposal="A ₹15 rain surge fee on every food order", audience="urban_online",
            size=60, rounds=2, seed=1, use_news=False)
    asyncio.run(run_simulation(r, Router(api_key="")))
    types = [e["type"] for e in r.events]
    assert types[0] == "init" and types[-1] == "done"
    assert "report" in types and "themes" in types and types.count("metrics") == 2
    assert r.result["final"]["n"] == 60
