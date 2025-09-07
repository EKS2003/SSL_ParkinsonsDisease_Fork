from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Assuming your ORM models and repository are accessible like this:
from repo.sql_models import Patient
from repo.patient_repository import PatientRepository

# Step 1: Set up the SQLAlchemy engine and session factory
engine = create_engine("sqlite:///test.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)

# Step 2: Use a session (context manager ensures it’s cleaned up)
with SessionLocal() as session:
    # Step 3: Instantiate the repository with the current session
    patient_repo = PatientRepository(session)

    # Example: Add a new patient
    new_patient = Patient(
        patient_id="P002",
        name="John Doe",
        dob=date(1970, 1, 1),
        height=170,
        weight=70,
    )
    patient_repo.add(new_patient)

    # Example: Retrieve a patient by ID
    patient = patient_repo.get("P002")
    print(f"Retrieved: {patient}")

    # Example: Update the patient's height
    updated_patient = patient_repo.update("P002", {"height": 175})
    print(f"Updated: {updated_patient}")

    # Example: List patients with pagination
    patients = patient_repo.list(skip=0, limit=10)
    print("All patients:", patients)

    # Example: Delete the patient
    was_deleted = patient_repo.delete("P002")
    print("Deletion successful:", was_deleted)
