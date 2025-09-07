from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from repo.sql_models import Patient

class PatientRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, patient_id: str) -> Optional[Patient]:
        # use session.get for primary-key lookup in SQLAlchemy 1.4+
        return self.session.get(Patient, patient_id)

    def add(self, patient: Patient) -> Patient:
        self.session.add(patient)
        # consider deferring commit to a higher layer
        self.session.commit()
        return patient

    def update(self, patient_id: str, update_data: Dict[str, Any]) -> Optional[Patient]:
        patient = self.get(patient_id)
        if patient is None:
            return None
        for key, value in update_data.items():
            if hasattr(patient, key):
                setattr(patient, key, value)
        self.session.commit()
        return patient

    def delete(self, patient_id: str) -> bool:
        patient = self.get(patient_id)
        if patient is None:
            return False
        self.session.delete(patient)
        self.session.commit()
        return True

    def list(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        return (
            self.session
            .query(Patient)
            .offset(skip)
            .limit(limit)
            .all()
        )

# Add more methods as needed for complex queries, filtering, etc.