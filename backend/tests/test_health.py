from app.db.session import get_db
from app.main import app


def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "reachable"}


def test_readiness_returns_503_when_database_fails(client):
    class BrokenSession:
        def execute(self, _statement):
            raise RuntimeError("database unavailable")

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not ready"
