import io
import json
from types import SimpleNamespace as NS

import anthropic
try:
    import httpx2 as httpx   # newer anthropic SDKs use httpx2
except ImportError:
    import httpx
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(pages):
    """pages: list of strings (empty string = blank page)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for t in pages:
        y = 800
        for line in t.split("\n"):
            if line:
                c.drawString(50, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def api_error(cls, status=429):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    if cls is anthropic.APIConnectionError:
        return cls(request=req)
    return cls("boom", response=httpx.Response(status, request=req), body=None)


# ---- fake SDK response objects ----
def text(t): return NS(type="text", text=t)
def tool_use(name, **inp): return NS(type="tool_use", name=name, input=inp)
def search_result(*urls):
    return NS(type="web_search_tool_result", content=[NS(url=u, title=f"Title {u}") for u in urls])
def resp(*blocks, stop="end_turn"): return NS(content=list(blocks), stop_reason=stop)


def verdict_json(verdict="Verified", real="ok", why="because", sources=None, conf="high"):
    return json.dumps({"verdict": verdict, "confidence": conf, "real_fact": real,
                       "explanation": why, "sources": sources or []})


class FakeClient:
    """messages.create(**kw) dispatches to handler(kw); records every call."""
    def __init__(self, handler):
        self.calls = []
        self.messages = NS(create=self._create)
        self._handler = handler

    def _create(self, **kw):
        self.calls.append(kw)
        out = self._handler(kw)
        if isinstance(out, Exception):
            raise out
        return out


def tools_of(kw): return [t.get("name") for t in kw.get("tools", [])]
