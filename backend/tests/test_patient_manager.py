import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repo.sql_models import Base, User
from repo.patient_repository import PatientRepository
from services.patient_service import PatientService, _parse_number
from core.exceptions import PatientValidationError


@pytest.fixture
def service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    u = User(
        username="doc",
        full_name="Dr. Test",
        email="doc@test.com",
        hashed_password="pw",
        location="UF",
        title="MD",
        speciality="Neurology",
    )
    session.add(u)
    session.commit()
    svc = PatientService(PatientRepository(session), session)
    yield svc, u.id
    session.close()


def test_validate_severity_valid(service):
    svc, _ = service
    for valid in ["low", "medium", "high", "Stage 1", "Stage 2", "Stage 5"]:
        errors = svc._validate({"severity": valid})
        assert "severity" not in errors, f"Expected {valid!r} to be valid"


def test_validate_severity_invalid(service):
    svc, _ = service
    for invalid in ["Stage 6", "none", "very high", "1", "Stage"]:
        errors = svc._validate({"severity": invalid})
        assert "severity" in errors, f"Expected {invalid!r} to be invalid"


def test_validate_height_weight(service):
    svc, _ = service
    assert "height" not in svc._validate({"height": 180})
    assert "weight" not in svc._validate({"weight": 70})
    assert "height" in svc._validate({"height": 400})
    assert "weight" in svc._validate({"weight": 600})


def test_parse_number():
    assert _parse_number(180, 0, 300) == 180.0
    assert _parse_number(400, 0, 300) is None
    assert _parse_number("170cm", 0, 300) == 170.0
    assert _parse_number(None, 0, 300) is None


def test_create_patient_mocked(service):
    from routes.contracts import PatientCreate
    svc, user_id = service
    data = PatientCreate(
        name="Test Patient",
        age=30,
        birthDate=date(1990, 1, 1),
        height=180.0,
        weight=80.0,
        severity="Stage 1",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    assert patient_id is not None
