from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_snapshot_mode_renders_without_exceptions(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "snapshot")
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Visão geral",
        "Séries históricas",
        "Qualidade dos dados",
        "Metodologia e fontes",
    ]
    assert len(app.metric) == 7
