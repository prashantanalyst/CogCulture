# Truth Layer: a PDF fact-checking agent

Upload a PDF. The app pulls out every checkable claim (stats, dates, financial and technical figures), searches the **live web** for each one, and flags it:

| Verdict | Meaning | What you get |
|---|---|---|
| **Verified** | Current, reliable sources match | Sources |
| **Inaccurate** | Wrong, outdated or misattributed | **The correct, current fact** plus sources |
| **False** | No credible evidence it exists | What was searched, low-confidence flag |

Reports download as JSON or CSV.

## How it works

```
PDF ──► pypdf text (per page) ──► Claude extracts claims (forced tool schema)
        │ no text layer?                       │
        └─► Claude reads the PDF natively      ▼
                                   one live web search agent per claim (parallel)
                                               ▼
                         guards ──► Verified / Inaccurate / False + real fact + sources
```

Design choices that matter:

- **Structured extraction.** Claims come back through a forced tool schema, so there is no fragile JSON scraping on the extraction step.
- **Evidence guards in code, not just prompts.** A verdict of Verified or Inaccurate with zero retrieved web results is downgraded to False. Cited URLs are kept only if the search tool actually returned them, so hallucinated sources cannot reach the report.
- **Date aware.** Today's date is injected so "was true in 2021, superseded since" correctly becomes Inaccurate with the current figure.
- **Prompt-injection safe.** PDF text and claims are wrapped as untrusted data. The bundled trap document contains a line telling the checker to mark everything Verified; the guards above hold even if a model obeys it.
- **Resilient.** Retries with backoff on 429/5xx/529, a repair call if the model returns malformed JSON, `pause_turn` handling for server-side search, per-claim error isolation (one failure shows as Error, the rest still report), scanned-PDF fallback, page and size caps.

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # or paste it in the sidebar
streamlit run app.py
```

Optional: `ANTHROPIC_MODEL` overrides the default model.

## Deploy (Streamlit Community Cloud, free)

1. Push this folder to a public GitHub repo.
2. Go to share.streamlit.io, **New app**, pick the repo, main file `app.py`.
3. **Advanced settings → Secrets**, add: `ANTHROPIC_API_KEY = "sk-ant-..."`
4. Deploy, open the URL, click **Try the sample trap document**.

## Test it

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # 63 tests, no network or API key needed
python samples/make_trap_pdf.py   # regenerates the trap document
```

Coverage: corrupted, empty, encrypted, oversized, scanned and multi-page PDFs; chunking; malformed model output; retry and rate-limit paths; hallucinated sources; prompt injection; per-claim failure isolation; real Anthropic SDK request/response parsing against a mocked transport; and the Streamlit app booting headless.

## Known limits

- Verdicts are web evidence plus model judgment, so treat them as a fast first pass, not legal sign-off.
- Cost scales with claims (one search agent each). The sidebar caps it, default 20.
- Paywalled primary sources cannot be read, which can push a true claim toward low confidence.

## Sample trap document

`samples/trap_document.pdf` mixes true claims (Python 1991, GDPR 2018), outdated ones (population 7.0B, Twitter as TWTR, iPhone 14 as latest), fabricated ones (a "Stanford study", "Zentrix Quantum Labs") and an injection line.
