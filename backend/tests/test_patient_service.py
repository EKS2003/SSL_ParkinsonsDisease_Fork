import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repo.sql_models import Base, User
from repo.patient_repository import PatientRepository
from routes.contracts import PatientCreate, PatientUpdate
from services.patient_service import PatientService
from core.exceptions import PatientNotFoundError, PatientValidationError


@pytest.fixture
def db():
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

    yield session, u.id
    session.close()


@pytest.fixture
def service(db):
    session, user_id = db
    return PatientService(PatientRepository(session), session), user_id


def test_create_patient_returns_id(service):
    svc, user_id = service
    data = PatientCreate(
        name="Alice",
        age=40,
        birthDate=date(1984, 1, 1),
        height=165.0,
        weight=60.0,
        severity="Stage 1",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    assert patient_id is not None
    assert isinstance(patient_id, str)


def test_create_patient_invalid_severity_raises(service):
    svc, user_id = service
    data = PatientCreate(
        name="Bob",
        age=50,
        birthDate=date(1974, 1, 1),
        height=170.0,
        weight=75.0,
        severity="Stage 99",
    )
    with pytest.raises(PatientValidationError) as exc_info:
        svc.create_patient(user_id=user_id, data=data)
    assert "severity" in exc_info.value.errors


def test_get_patient_not_found_raises(service):
    svc, _ = service
    with pytest.raises(PatientNotFoundError):
        svc.get_patient("nonexistent-id")


def test_get_patient_returns_response(service):
    svc, user_id = service
    data = PatientCreate(
        name="Carol",
        age=35,
        birthDate=date(1989, 6, 15),
        height=160.0,
        weight=55.0,
        severity="Stage 2",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    resp = svc.get_patient(patient_id)
    assert resp.name == "Carol"
    assert resp.patient_id == patient_id


def test_update_patient(service):
    svc, user_id = service
    data = PatientCreate(
        name="Dave",
        age=60,
        birthDate=date(1964, 3, 10),
        height=180.0,
        weight=85.0,
        severity="Stage 3",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    svc.update_patient(patient_id, PatientUpdate(severity="Stage 4"))
    resp = svc.get_patient(patient_id)
    assert resp.severity == "Stage 4"


def test_delete_patient(service):
    svc, user_id = service
    data = PatientCreate(
        name="Eve",
        age=45,
        birthDate=date(1979, 9, 20),
        height=158.0,
        weight=52.0,
        severity="Stage 1",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    svc.delete_patient(patient_id)
    with pytest.raises(PatientNotFoundError):
        svc.get_patient(patient_id)


def test_list_patients(service):
    svc, user_id = service
    for i in range(3):
        svc.create_patient(
            user_id=user_id,
            data=PatientCreate(
                name=f"Patient {i}",
                age=30 + i,
                birthDate=date(1990, 1, 1),
                height=170.0,
                weight=70.0,
                severity="Stage 1",
            ),
        )
    result = svc.list_patients(skip=0, limit=100)
    assert result["total"] >= 3


def test_search_patients(service):
    svc, user_id = service
    svc.create_patient(
        user_id=user_id,
        data=PatientCreate(
            name="Unique Search Name",
            age=55,
            birthDate=date(1969, 1, 1),
            height=172.0,
            weight=78.0,
            severity="Stage 2",
        ),
    )
    results = svc.search_patients("Unique Search Name")
    assert any(p.name == "Unique Search Name" for p in results)
