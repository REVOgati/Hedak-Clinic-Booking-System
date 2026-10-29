import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from app.database import Base, get_db
from app.main import app

# Use an in-memory SQLite database for fast unit testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_root_docs():
    response = client.get("/docs")
    assert response.status_code == 200

def test_booking_validation_time_in_past():
    # Attempt to book a time in the past should fail
    past_time = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    response = client.post("/appointments", json={
        "doctor_id": 1,
        "patient_id": 1,
        "start_time": past_time
    })
    assert response.status_code == 400