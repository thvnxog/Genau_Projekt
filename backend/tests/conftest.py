from pathlib import Path
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    # Macht Imports wie `from app import create_app` aus dem Backend-Ordner möglich.
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def app(monkeypatch, tmp_path):
    # Jede Testausführung bekommt eine frische, temporäre Datenbank.
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    )

    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture()
def client(app):
    # Der Test-Client sendet Anfragen an die Flask-App, ohne einen echten Server zu starten.
    return app.test_client()