from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from repo.sql_models import Visit


class VisitRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def getall(self, patient_id: str) -> List[Visit]:
        return (
            self.session
            .query(Visit)
            .filter(Visit.patient_id == patient_id)
            .order_by(Visit.visit_date.desc())
            .all()
        )

    def get(self, visit_id: str) -> Optional[Visit]:
        # use session.get for primary-key lookup in SQLAlchemy 1.4+
        return self.session.get(Visit, visit_id)

    def add(self, visit: Visit) -> Visit:
        self.session.add(visit)
        # consider deferring commit to a higher layer
        self.session.commit()
        return visit

    def update(self, visit_id: str, update_data: Dict[str, Any]) -> Optional[Visit]:
        visit = self.get(visit_id)
        if visit is None:
            return None
        for key, value in update_data.items():
            if hasattr(visit, key):
                setattr(visit, key, value)
        self.session.commit()
        return visit

    def delete(self, visit_id: str) -> bool:
        visit = self.get(visit_id)
        if visit is None:
            return False
        self.session.delete(visit)
        self.session.commit()
        return True

    def list(self, patient_id: str | None = None, skip: int = 0, limit: int = 100):
        q = self.session.query(Visit)
        if patient_id:
            q = q.filter(Visit.patient_id == patient_id)
        return q.order_by(Visit.visit_date.asc()).offset(skip).limit(limit).all()