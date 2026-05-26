from pathlib import Path
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    )

    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()