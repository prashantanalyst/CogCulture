from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional

VERDICTS = ("Verified", "Inaccurate", "False")
CATEGORIES = ("statistic", "date", "financial", "technical", "other")


@dataclass
class Claim:
    id: int
    text: str
    category: str = "other"
    page: Optional[int] = None
    context: str = ""


@dataclass
class Source:
    title: str
    url: str


@dataclass
class Result:
    claim: Claim
    verdict: str = "Error"          # Verified | Inaccurate | False | Error
    confidence: str = "low"
    real_fact: str = ""
    explanation: str = ""
    sources: list = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Report:
    results: list
    total_pages: int = 0
    truncated: bool = False
    used_native_pdf: bool = False
    warnings: list = field(default_factory=list)

    def counts(self):
        out = {"Verified": 0, "Inaccurate": 0, "False": 0, "Error": 0}
        for r in self.results:
            out[r.verdict if r.verdict in out else "Error"] += 1
        return out

    def to_dict(self):
        return {"counts": self.counts(), "total_pages": self.total_pages,
                "truncated": self.truncated, "warnings": self.warnings,
                "results": [r.to_dict() for r in self.results]}
