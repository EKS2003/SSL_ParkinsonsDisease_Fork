import pytest
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from repo.sql_models import Base, Patient, User, TestResult
from repo.patient_repository import PatientRepository

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Seed data
    u = User(username="test", full_name="Test User", email="test@test.com", hashed_password="pw", location="x", title="y", speciality="z")
    session.add(u)
    session.commit()
    
    p1 = Patient(patient_id="P1", user_id=u.id, name="Alice", dob=date(1990, 1, 1), severity="Stage 1")
    p2 = Patient(patient_id="P2", user_id=u.id, name="Bob", dob=date(1980, 1, 1), severity="Stage 2")
    p3 = Patient(patient_id="P3", user_id=u.id, name="Charlie", dob=date(1970, 1, 1), severity="Stage 3")
    
    session.add_all([p1, p2, p3])
    session.commit()
    
    yield session
    session.close()

def test_filter_patients_severity(session):
    repo = PatientRepository(session)
    
    # Filter Stage 1
    res = repo.filter_patients(severity="Stage 1")
    assert len(res) == 1
    assert res[0].name == "Alice"
    
    # Filter Stage 3
    res = repo.filter_patients(severity="Stage 3")
    assert len(res) == 1
    assert res[0].name == "Charlie"
    
    # Filter None (returns all)
    res = repo.filter_patients(severity=None)
    assert len(res) == 3

def test_add_test_result(session):
    repo = PatientRepository(session)
    
    # Add a test result using the updated parameters
    dt = datetime.now()
    t = repo.add_test_result(
        patient_id="P1",
        test_name="finger-tapping",
        test_date=dt,
        recording_file="test.mp4",
        frame_count=100
    )
    
    assert t.patient_id == "P1"
    assert t.test_name == "finger-tapping"
    assert t.recording_file == "test.mp4"
    assert t.frame_count == 100
    
    # Verify in DB
    db_t = session.query(TestResult).filter_by(patient_id="P1").first()
    assert db_t is not None
    assert db_t.test_name == "finger-tapping"
    assert db_t.frame_count == 100
