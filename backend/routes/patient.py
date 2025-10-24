from fastapi import APIRouter, Depends, Query, HTTPException

from datetime import date
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import json, re


from patient_manager import (
    async_create_patient, async_get_patient_info,
    async_update_patient_info, async_delete_patient_record,
    async_get_all_patients_info, async_search_patients,
    async_filter_patients,
)

_num = re.compile(r"(\d+\.?\d*)")
# Accept low/medium/high OR Stage 1..5

class PatientCreate(BaseModel):
    name: str
    birthDate: date                                      # <-- use birthDate not age
    height: Optional[Union[float, str]] = None
    weight: Optional[Union[float, str]] = None
    lab_results: Union[str, Dict[str, Any]] = Field(default_factory=dict)    
    doctors_notes: Optional[str] = ""
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

    @field_validator("lab_results", mode="before")
    @classmethod
    def coerce_lab_results(cls, v):
        if v is None: return {}
        if isinstance(v, dict): return v
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {"value": parsed}
            except Exception:
                return {"value": v}
        return {"value": v}

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    birthDate: Optional[date] = None                     # <-- keep birthDate for updates too
    height: Optional[Union[float, str]] = None
    weight: Optional[Union[float, str]] = None
    lab_results: Union[str, Dict[str, Any]] = Field(default_factory=dict)    
    doctors_notes: Optional[str] = None
    doctors_notes_history: Optional[List[Dict[str, Any]]] = None
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

    @field_validator("lab_results", mode="before")
    @classmethod
    def _to_dict(cls, v):
        if v in (None, ""):
            return None
        if isinstance(v, dict):
            return v
        try:
            parsed = json.loads(str(v))
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            return {"value": v}

class PatientResponse(BaseModel):
    patient_id: str
    name: str
    birthDate: str
    height: str
    weight: str
    doctors_notes: str
    severity: str
    lab_results: Dict[str, Any] = Field(default_factory=dict)
    lab_results_history: List[Dict[str, Any]] = Field(default_factory=list)   # <-- add
    doctors_notes_history: List[Dict[str, Any]] = Field(default_factory=list)


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

router = APIRouter(prefix="/patients")


@router.post("/", response_model=Dict)
async def create_patient(patient: PatientCreate):
    result = await async_create_patient(
        name=patient.name,
        birthDate=patient.birthDate,
        height=patient.height,
        weight=patient.weight,
        lab_results=patient.lab_results or {},
        doctors_notes=patient.doctors_notes or "",
        severity=patient.severity,
    )

    if not result or not result.get("success"):
        # Prefer detailed errors if present
        detail = result.get("errors") if result and result.get("errors") else result.get("error", "Failed to create patient")
        raise HTTPException(status_code=422 if isinstance(detail, dict) else 400, detail=detail)

    return result

@router.get("/", response_model=PatientsListResponse)
async def get_patients(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000)
):
    return await async_get_all_patients_info(skip, limit)

@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: str):
    result = await async_get_patient_info(patient_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Patient not found")
    return result["patient"]

@router.put("/{patient_id}", response_model=Dict)
async def update_patient(patient_id: str, patient_update: PatientUpdate):
    update_data = patient_update.model_dump(exclude_unset=True)
    if update_data.get("lab_results") == {}:
        update_data.pop("lab_results")
    if not update_data:
        return {"success": True, "patient_id": patient_id}  # no-op instead of 400

    result = await async_update_patient_info(patient_id, update_data)
    if not result.get("success"):
        if "errors" in result:
            raise HTTPException(status_code=400, detail=result["errors"])
        raise HTTPException(status_code=404, detail=result.get("error", "Failed to update patient"))
    return result

@router.delete("/{patient_id}", response_model=Dict)
async def delete_patient(patient_id: str):
    result = await async_delete_patient_record(patient_id)

    if not result.get("success", False):
        raise HTTPException(status_code=404, detail="Patient not found")

    return result

@router.get("/search/{query}", response_model=PatientSearchResponse)
async def search_patients_endpoint(query: str):
    return await async_search_patients(query)

@router.post("/filter/", response_model=PatientSearchResponse)
async def filter_patients_endpoint(criteria: FilterCriteria):
    return await async_filter_patients(criteria.dict(exclude_none=True))
