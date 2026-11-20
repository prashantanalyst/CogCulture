import threading
from factcheck import config
from factcheck.pipeline import run_factcheck
from factcheck.pdf_extract import PDFError
import pytest
from .helpers import FakeClient, make_pdf, resp, text, tool_use, search_result, verdict_json, tools_of

PDF = make_pdf(["Python was first released in 1991 and is popular.\nThe world population is 7.0 billion people.\nZentrix raised 4.2B."])
CLAIMS = [{"text": "Python was first released in 1991.", "category": "date", "page": 1},
          {"text": "The world population is 7.0 billion people.", "category": "statistic", "page": 1},
          {"text": "Zentrix raised 4.2 billion dollars.", "category": "financial", "page": 1}]


def handler(kw):
    names = tools_of(kw)
    if "report_claims" in names:
        return resp(tool_use("report_claims", claims=CLAIMS))
    claim = kw["messages"][0]["content"]
    if "Python" in claim:
        return resp(search_result("https://python.org/"), text(verdict_json("Verified")))
    if "population" in claim:
        return resp(search_result("https://un.org/"), text(verdict_json("Inaccurate", "8.2 billion (2025)", "outdated")))
    return resp(search_result("https://x.com/"), text(verdict_json("False", "No evidence found", "no such round")))


def test_end_to_end_flags_each_class_in_order():
    rep = run_factcheck(PDF, FakeClient(handler), model="m")
    assert [r.verdict for r in rep.results] == ["Verified", "Inaccurate", "False"]
    assert rep.counts() == {"Verified": 1, "Inaccurate": 1, "False": 1, "Error": 0}
    assert "8.2" in rep.results[1].real_fact


def test_one_failing_claim_does_not_sink_report():
    def h(kw):
        if "Zentrix" in str(kw["messages"][0]["content"]) and "report_claims" not in tools_of(kw):
            raise RuntimeError("boom")
        return handler(kw)
    rep = run_factcheck(PDF, FakeClient(h), model="m")
    assert rep.counts()["Error"] == 1 and rep.counts()["Verified"] == 1
    assert rep.results[2].error and rep.results[2].verdict == "Error"


def test_progress_runs_on_calling_thread_and_reaches_total():
    main, seen = threading.get_ident(), []
    def prog(stage, done, total, msg): seen.append((threading.get_ident(), stage, done, total))
    run_factcheck(PDF, FakeClient(handler), model="m", progress=prog)
    assert all(t == main for t, *_ in seen)
    assert seen[-1][1:] == ("verify", 3, 3)


def test_no_claims_found_returns_warning_not_crash():
    c = FakeClient(lambda kw: resp(tool_use("report_claims", claims=[])))
    rep = run_factcheck(PDF, c, model="m")
    assert rep.results == [] and any("No checkable claims" in w for w in rep.warnings)


def test_scanned_pdf_uses_native_path():
    c = FakeClient(handler)
    rep = run_factcheck(make_pdf(["", ""]), c, model="m")
    assert rep.used_native_pdf and any("No text layer" in w for w in rep.warnings)
    assert c.calls[0]["messages"][0]["content"][0]["type"] == "document"
    assert len(rep.results) == 3


def test_truncation_warning(monkeypatch):
    monkeypatch.setattr(config, "MAX_PAGES", 1)
    rep = run_factcheck(make_pdf(["Python was first released in 1991 ok yes", "page two text here"]), FakeClient(handler), model="m")
    assert rep.truncated and any("first 1 of 2" in w for w in rep.warnings)


def test_bad_pdf_raises_pdferror():
    with pytest.raises(PDFError):
        run_factcheck(b"nope", FakeClient(handler), model="m")


def test_max_claims_limit_respected():
    many = [{"text": f"Claim {i} says growth was {i}0% in 20{i}0"} for i in range(1, 9)]
    def h(kw):
        return resp(tool_use("report_claims", claims=many)) if "report_claims" in tools_of(kw) else handler(kw)
    rep = run_factcheck(PDF, FakeClient(h), model="m", max_claims=3)
    assert len(rep.results) == 3


def test_report_serializes_to_json():
    import json
    rep = run_factcheck(PDF, FakeClient(handler), model="m")
    d = json.loads(json.dumps(rep.to_dict()))
    assert d["counts"]["Inaccurate"] == 1 and d["results"][0]["claim"]["id"] == 1
