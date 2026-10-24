from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_without_db_or_key():
    app = create_app(Settings(_env_file=None, database_url="", gemini_api_key=""))
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "not_configured", "gemini": "missing"}
