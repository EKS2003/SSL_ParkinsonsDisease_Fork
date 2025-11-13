from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import json, re
from datetime import datetime, date
from pydantic import ConfigDict  # v2


_num = re.compile(r"(\d+\.?\d*)")


class LabResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(validation_alias='lab_id', serialization_alias='id')
    date: Optional[datetime] = Field(None, validation_alias='result_date', serialization_alias='date')
    results: Optional[str] = None
    added_by: Optional[str] = None  # drop if you don't store it

class DoctorNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(validation_alias='note_id', serialization_alias='id')
    date: Optional[datetime] = Field(None, validation_alias='note_date', serialization_alias='date')
    note: str = ""
    added_by: Optional[str] = None


class PatientCreate(BaseModel):
    name: str
    age: int    
    birthDate: date                                      # <-- use birthDate not age
    height: Optional[Union[float, str]] = None
    weight: Optional[Union[float, str]] = None
    lab_results_history: List[LabResultOut]  # <-- change here
    doctors_notes_history: List[DoctorNoteOut] 
    severity: str

    @field_validator("height", "weight", mode="before")
    @classmethod
    def _to_float(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        m = _num.search(str(v))
        return float(m.group(1)) if m else None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    birthDate: Optional[date] = None                     # <-- keep birthDate for updates too
    height: Optional[Union[float, str]] = None
    weight: Optional[Union[float, str]] = None
    lab_results: Optional[Union[str, Dict[str, Any]]] = None  # <- make optional
    doctors_notes: Optional[List[Dict[str, Any]]] = None
    severity: Optional[str] = None

    @field_validator("height", "weight", mode="before")
    @classmethod
    def _to_float(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        m = _num.search(str(v))
        return float(m.group(1)) if m else None



class PatientResponse(BaseModel):
    patient_id: str
    name: str
    birthDate: str
    height: str
    weight: str
    doctors_notes: Optional[DoctorNoteOut] = None   # latest can be missing
    severity: str
    lab_results: Optional[LabResultOut] = None      # latest can be missing
    lab_results_history: List[LabResultOut] = []
    doctors_notes_history: List[DoctorNoteOut] = []


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
    # Keep age filters if you want; you’ll compute DOB cutoffs server-side
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    severity: Optional[str] 
