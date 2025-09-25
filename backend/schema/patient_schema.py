from pydantic import BaseModel, Field
from datetime import datetime,date
from typing import Dict, List, Optional


class PatientBase(BaseModel):
    name: Optional[str] = None
    dob: Optional[date] = None
    height: Optional[int] = None
    weight: Optional[int] = None

class PatientCreate(PatientBase):
    patient_id: str

class PatientUpdate(PatientBase):
    pass

class PatientResponse(PatientBase):
    patient_id: str
    class Config:
        orm_mode = True

class PatientsListResponse(BaseModel):
    success: bool
    patients: List[PatientResponse]
    total: int
    skip: int
    limit: int

class PatientSearchResponse(BaseModel):
    success: bool
    patients: List[PatientResponse]
    count: int

class FilterCriteria(BaseModel):
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    severity: Optional[str] = None
