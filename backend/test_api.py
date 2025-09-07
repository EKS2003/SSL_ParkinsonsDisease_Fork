import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app, get_db
from repo.sql_models import Base

@pytest.fixture
def client(tmp_path):
    # Create a temporary DB for each test
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # Define a dependency override for get_db
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Override FastAPI dependency
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    # Optional: clean up overrides after test
    app.dependency_overrides.pop(get_db, None)
# test file
import uuid

def test_create_and_get_patient(client):
    unique_id = f"P{uuid.uuid4().hex}"
    # create
    resp = client.post("/patients/", json={"patient_id": unique_id, "name": "Eve"})
    assert resp.status_code == 201  # or adjust to 200 if you don't set status_code=201
    # get
    get_resp = client.get(f"/patients/{unique_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["patient_id"] == unique_id
    # delete
    del_resp = client.delete(f"/patients/{unique_id}")
    assert del_resp.status_code == 204  # set status_code=204 on the endpoint
    # get again should 404
    assert client.get(f"/patients/{unique_id}").status_code == 404
