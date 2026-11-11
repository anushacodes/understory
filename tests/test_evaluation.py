from app.evaluate import score


def test_relevance_units_deduplicate_and_mrr_uses_first_hit():
    units = [
        {"path": "a.py", "start_line": 10, "end_line": 20},
        {"path": "b.py", "start_line": 1, "end_line": 8},
    ]
    hits = [
        {"path": "irrelevant.py", "start_line": 1, "end_line": 50},
        {"path": "a.py", "start_line": 8, "end_line": 12},
        {"path": "a.py", "start_line": 10, "end_line": 20},
    ]
    assert score(hits, units) == (0.5, 0.5)
    assert score(hits, []) == (None, None)
