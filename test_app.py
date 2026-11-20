from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_loads_cleanly(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("Truth Layer" in m.value for m in at.markdown)


def test_sample_without_key_shows_friendly_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    sample = [b for b in at.button if "sample" in b.label.lower()][0]
    at = sample.click().run()
    assert not at.exception
    assert any("API key" in e.value for e in at.error)
