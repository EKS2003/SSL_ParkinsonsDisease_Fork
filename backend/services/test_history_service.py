from datetime import datetime
from sqlalchemy.orm import Session

from repo.sql_models import TestResult


class TestHistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_patient_tests(self, patient_id: str) -> list[TestResult]:
        return (
            self.db.query(TestResult)
            .filter(TestResult.patient_id == patient_id)
            .all()
        )

    def add_patient_test(self, patient_id: str, test_data: dict) -> TestResult:
        record = TestResult(
            patient_id=patient_id,
            test_name=test_data.get("test_name"),
            test_date=test_data.get("date"),
            recording_file=test_data.get("recording_file"),
            frame_count=test_data.get("frame_count"),
        )
        self.db.add(record)
        self.db.commit()
        return record

    def get_all_tests(self) -> list[TestResult]:
        return self.db.query(TestResult).all()
