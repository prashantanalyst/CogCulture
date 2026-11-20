import os

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}

MAX_PDF_MB = 15
MAX_PAGES = 60
CHUNK_CHARS = 30_000
MIN_TEXT_CHARS = 40
DEFAULT_MAX_CLAIMS = 20
HARD_MAX_CLAIMS = 40
WORKERS = 4
MAX_RETRIES = 4
