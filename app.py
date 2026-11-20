"""Truth Layer: upload a PDF, get every checkable claim verified against the live web."""
import csv
import io
import json
import os
from pathlib import Path

import streamlit as st

from factcheck import config
from factcheck.llm import friendly_error, make_client
from factcheck.pdf_extract import PDFError
from factcheck.pipeline import run_factcheck

st.set_page_config(page_title="Truth Layer | PDF Fact-Checker", page_icon="🔎", layout="wide")

SAMPLE = Path(__file__).parent / "samples" / "trap_document.pdf"
STYLE = {  # verdict: (text, background, glyph)
    "Verified": ("#0F7B5A", "#E3F8F0", "✓"),
    "Inaccurate": ("#9A5B00", "#FFF3D6", "!"),
    "False": ("#B42318", "#FFE8E5", "✕"),
    "Error": ("#475467", "#EEF0F4", "?"),
}
st.markdown("""
<style>
.block-container{padding-top:2rem;max-width:1100px}
.hero h1{font-size:2.6rem;margin:0;letter-spacing:-0.02em}
.hero p{color:#5B6478;font-size:1.1rem;margin-top:.3rem}
.badge{display:inline-block;padding:.15rem .7rem;border-radius:999px;font-weight:700;font-size:.85rem}
.claim{font-size:1.05rem;font-weight:600;margin:.35rem 0 .2rem}
.fact{background:#F2F4F8;border-radius:10px;padding:.7rem .9rem;margin:.4rem 0}
.kpi{border-radius:14px;padding:1rem 1.2rem}
.kpi b{font-size:2rem;display:block;line-height:1.1}
</style>""", unsafe_allow_html=True)


def secret_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or ""
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY", "")


def badge(v):
    fg, bg, g = STYLE.get(v, STYLE["Error"])
    return f'<span class="badge" style="color:{fg};background:{bg}">{g} {v}</span>'


def to_csv(report):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "page", "category", "claim", "verdict", "confidence", "correct_fact", "explanation", "sources"])
    for r in report.results:
        w.writerow([r.claim.id, r.claim.page or "", r.claim.category, r.claim.text, r.verdict, r.confidence,
                    r.real_fact, r.explanation, " | ".join(s.url for s in r.sources)])
    return buf.getvalue()


with st.sidebar:
    st.header("Settings")
    user_key = st.text_input("Anthropic API key", type="password",
                             help="Optional if the app owner configured a key. Never stored.")
    max_claims = st.slider("Max claims to check", 5, config.HARD_MAX_CLAIMS, config.DEFAULT_MAX_CLAIMS,
                           help="Each claim triggers its own live web search.")
    st.caption(f"Model: `{config.MODEL}`")
    st.divider()
    st.markdown("**Verdicts**\n\n- **Verified**: current sources match\n- **Inaccurate**: wrong or outdated, with the real fact\n- **False**: no evidence it exists")

st.markdown('<div class="hero"><h1>🔎 Truth Layer</h1>'
            '<p>Drop in a PDF. Every stat, date and figure gets checked against the live web, '
            'and wrong ones come back with the real fact.</p></div>', unsafe_allow_html=True)
st.write("")

up = st.file_uploader("Upload a PDF", type=["pdf"])
c1, c2 = st.columns([1, 1])
run = c1.button("Run fact-check", type="primary", disabled=up is None, use_container_width=True)
use_sample = c2.button("Try the sample trap document", disabled=not SAMPLE.exists(), use_container_width=True)

if run or use_sample:
    key = user_key or secret_key()
    if not key:
        st.error("No API key found. Add one in the sidebar, or set ANTHROPIC_API_KEY in the app secrets.")
    else:
        data = up.getvalue() if (run and up is not None) else SAMPLE.read_bytes()
        name = up.name if (run and up is not None) else SAMPLE.name
        bar = st.progress(0.0)
        with st.status("Working…", expanded=True) as status:
            def progress(stage, done, total, msg):
                base = {"read": 0.0, "extract": 0.1, "verify": 0.2}[stage]
                bar.progress(min(1.0, base + (0.8 if stage == "verify" else 0.1) * done / max(total, 1)))
                status.update(label=msg)
            try:
                report = run_factcheck(data, make_client(key), max_claims=max_claims, progress=progress)
                st.session_state["report"], st.session_state["name"] = report, name
                status.update(label="Done", state="complete", expanded=False)
            except PDFError as e:
                status.update(label="Could not read the PDF", state="error")
                st.error(str(e))
            except Exception as e:
                status.update(label="Something went wrong", state="error")
                st.error(friendly_error(e))
        bar.empty()

report = st.session_state.get("report")
if report:
    st.subheader(f"Report: {st.session_state.get('name', '')}")
    for w in report.warnings:
        st.warning(w)
    counts = report.counts()
    cols = st.columns(4)
    for col, v in zip(cols, ["Verified", "Inaccurate", "False", "Error"]):
        fg, bg, _ = STYLE[v]
        col.markdown(f'<div class="kpi" style="background:{bg};color:{fg}"><b>{counts[v]}</b>{v}</div>',
                     unsafe_allow_html=True)
    total = len(report.results)
    if total:
        st.write("")
        st.caption(f"{counts['Verified']} of {total} claims hold up. "
                   f"{counts['Inaccurate'] + counts['False']} need attention.")
        shown = st.multiselect("Show", ["Verified", "Inaccurate", "False", "Error"],
                               default=["Inaccurate", "False", "Error", "Verified"])
        order = {"False": 0, "Inaccurate": 1, "Error": 2, "Verified": 3}
        for r in sorted(report.results, key=lambda r: (order.get(r.verdict, 9), r.claim.id)):
            if r.verdict not in shown:
                continue
            with st.container(border=True):
                head = f"{badge(r.verdict)} &nbsp; <span style='color:#8A93A8'>" \
                       f"{r.claim.category} · page {r.claim.page or '?'} · confidence {r.confidence}</span>"
                st.markdown(head, unsafe_allow_html=True)
                st.markdown(f'<div class="claim">{r.claim.text}</div>', unsafe_allow_html=True)
                if r.verdict == "Error":
                    st.caption(r.error or r.explanation)
                    continue
                if r.verdict != "Verified" and r.real_fact:
                    st.markdown(f'<div class="fact"><b>The real fact:</b> {r.real_fact}</div>', unsafe_allow_html=True)
                if r.explanation:
                    st.write(r.explanation)
                if r.sources:
                    st.markdown("Sources: " + " · ".join(f"[{s.title}]({s.url})" for s in r.sources))
        d1, d2 = st.columns(2)
        d1.download_button("Download JSON", json.dumps(report.to_dict(), indent=2), "factcheck_report.json",
                           "application/json", use_container_width=True)
        d2.download_button("Download CSV", to_csv(report), "factcheck_report.csv", "text/csv",
                           use_container_width=True)
st.caption("Verdicts come from live web search plus model judgment. Treat them as a fast first pass and review sources before publishing.")
