from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import config
from .extract import extract_claims, extract_claims_native_pdf
from .llm import friendly_error
from .models import Report, Result
from .pdf_extract import read_pdf
from .verify import verify_claim


def run_factcheck(pdf_bytes, client, *, model=config.MODEL, max_claims=config.DEFAULT_MAX_CLAIMS,
                  workers=config.WORKERS, progress=None, today=None) -> Report:
    """progress(stage, done, total, message) is always called from the calling thread."""
    note = progress or (lambda *a, **k: None)
    note("read", 0, 1, "Reading PDF")
    doc = read_pdf(pdf_bytes)
    warnings, native = [], False
    if doc.truncated:
        warnings.append(f"Only the first {config.MAX_PAGES} of {doc.total_pages} pages were checked.")

    note("extract", 0, 1, "Finding checkable claims")
    if doc.text_chars < config.MIN_TEXT_CHARS:
        native = True
        warnings.append("No text layer found (scanned PDF?). Claims were read with the model's PDF vision instead.")
        claims = extract_claims_native_pdf(pdf_bytes, client, model, max_claims)
    else:
        claims = extract_claims(doc, client, model, max_claims)
    if not claims:
        warnings.append("No checkable claims (stats, dates, figures) were found in this document.")
        return Report([], doc.total_pages, doc.truncated, native, warnings)

    results = [None] * len(claims)
    note("verify", 0, len(claims), f"Verifying {len(claims)} claims on the live web")

    def work(c):
        try:
            return verify_claim(c, client, model, today)
        except Exception as e:  # one bad claim must never sink the whole report
            return Result(claim=c, verdict="Error", error=friendly_error(e),
                          explanation="Verification failed for this claim. Re-run to retry.")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(work, c): i for i, c in enumerate(claims)}
        for done, f in enumerate(as_completed(futs), start=1):
            results[futs[f]] = f.result()
            note("verify", done, len(claims), f"Verified {done} of {len(claims)}")
    return Report(results, doc.total_pages, doc.truncated, native, warnings)
