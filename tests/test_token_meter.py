from engine.cache import SolveCache, fingerprint
from engine.token_meter import CallRecord, TokenMeter


def test_shared_solver_tokens_amortized_across_sibling_reports():
    m = TokenMeter()
    m.record(CallRecord("solver", "gpt-4o", "q1", None, 900, 300, 1200))
    m.record(CallRecord("solution_reader", "gpt-4o", "q1", None, 500, 100, 600))
    for rid in ("R1", "R2", "R3"):
        m.record(CallRecord("interpreter", "gpt-4o-mini", "q1", rid, 200, 50, 250))
        m.record(CallRecord("comparator", "gpt-4o", "q1", rid, 1500, 200, 1700))
        m.record(CallRecord("reply", "gpt-4o-mini", "q1", rid, 300, 60, 360))

    r1 = m.report_tokens("R1", "q1", 3)
    assert r1["question_shared_total"] == 1800
    assert r1["question_shared_allocated"] == 600
    assert r1["total_allocated"] == 250 + 1700 + 360 + 600

    s = m.summary({"R1": {"route": "auto_apply"}, "R2": {"route": "auto_apply"}, "R3": {"route": "no_change"}},
                  {"q1": ["R1", "R2", "R3"]})
    assert s["run_totals"]["total_tokens"] == 1800 + 3 * (250 + 1700 + 360)
    assert s["by_questionId"]["q1"]["shared_tokens"] == 1800
    assert s["by_questionId"]["q1"]["route_mix"] == {"auto_apply": 2, "faculty_review": 0, "no_change": 1}
    assert s["run_totals"]["estimated_usd"] > 0


def test_cache_hit_counts_zero_new_tokens():
    m = TokenMeter()
    m.record(CallRecord("solver", "gpt-4o", "q1", None, cache_hit=True))
    s = m.summary()
    assert s["run_totals"]["total_tokens"] == 0
    assert s["run_totals"]["cache_hits"] == 1
    assert s["run_totals"]["calls"] == 0


def test_fingerprint_changes_with_content_prompt_and_model(dataset, tmp_path):
    p = dataset.payloads["60f744b3f1b9bc7cc7b4a949"]
    base = fingerprint(p, "solver", "v1", "gpt-4o")
    assert base == fingerprint(p, "solver", "v1", "gpt-4o")
    assert base != fingerprint(p, "solver", "v2", "gpt-4o")
    assert base != fingerprint(p, "solver", "v1", "gpt-4.1")
    edited = p.model_copy(update={"question_html": p.question_html.replace("60 V", "70 V")})
    assert base != fingerprint(edited, "solver", "v1", "gpt-4o")

    cache = SolveCache(tmp_path)
    assert cache.get("solver", base) is None
    cache.put("solver", base, {"final_answer": "A"})
    assert cache.get("solver", base) == {"final_answer": "A"}
