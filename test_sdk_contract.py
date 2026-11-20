"""Runs the REAL anthropic SDK against a mocked HTTP transport, so request validation and
response parsing (including web_search_tool_result blocks) are exercised without network or a key."""
import json
import anthropic
try:
    import httpx2 as httpx   # newer anthropic SDKs use httpx2
except ImportError:
    import httpx
from factcheck.pipeline import run_factcheck
from .helpers import make_pdf


def message(content, stop="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "m", "content": content,
            "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 5, "output_tokens": 5}}


def handler_factory(log):
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        log.append(body)
        names = [t.get("name") for t in body.get("tools", [])]
        if "report_claims" in names:
            return httpx.Response(200, json=message([{
                "type": "tool_use", "id": "toolu_1", "name": "report_claims",
                "input": {"claims": [{"text": "The world population is 7.0 billion people.", "category": "statistic", "page": 1}]}}],
                stop="tool_use"))
        verdict = {"verdict": "Inaccurate", "confidence": "high", "real_fact": "About 8.2 billion in 2025 (UN).",
                   "explanation": "Outdated.", "sources": [{"title": "UN", "url": "https://population.un.org/wpp/"}]}
        return httpx.Response(200, json=message([
            {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "world population"}},
            {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": [
                {"type": "web_search_result", "url": "https://population.un.org/wpp/", "title": "UN WPP",
                 "encrypted_content": "abc", "page_age": None}]},
            {"type": "text", "text": json.dumps(verdict)}]))
    return handler


def test_real_sdk_roundtrip():
    log = []
    client = anthropic.Anthropic(api_key="test", max_retries=0,
                                 http_client=httpx.Client(transport=httpx.MockTransport(handler_factory(log))))
    rep = run_factcheck(make_pdf(["The world population is 7.0 billion people. Source: Nimbus brief."]), client, model="claude-test")
    r = rep.results[0]
    assert r.verdict == "Inaccurate" and "8.2" in r.real_fact
    assert r.sources and r.sources[0].url == "https://population.un.org/wpp/"
    verify_req = [b for b in log if "web_search" in [t.get("name") for t in b.get("tools", [])]][0]
    assert verify_req["tools"][0]["type"] == "web_search_20250305" and verify_req["model"] == "claude-test"
    extract_req = [b for b in log if "report_claims" in [t.get("name") for t in b.get("tools", [])]][0]
    assert extract_req["tool_choice"] == {"type": "tool", "name": "report_claims"}
