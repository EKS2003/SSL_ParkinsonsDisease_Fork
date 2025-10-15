from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from patient_manager import (
    Patient, PatientManager,
    async_create_patient, async_get_patient_info,
    async_update_patient_info, async_delete_patient_record,
    async_get_all_patients_info, async_search_patients,
    async_filter_patients,
    TestHistoryManager
)

class PatientCreate(BaseModel):
    name: str
    age: int = Field(..., ge=0, le=120)
    height: str = Field(..., min_length=1)
    weight: str = Field(..., min_length=1)
    lab_results: Optional[Dict] = Field(default_factory=dict)
    doctors_notes: Optional[str] = ""
    severity: str = Field("low", pattern="^(low|medium|high)$")

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=120)
    birthDate: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    lab_results: Optional[Dict] = None
    lab_results_history: Optional[List[Dict]] = None
    doctors_notes: Optional[str] = None
    doctors_notes_history: Optional[List[Dict]] = None
    severity: Optional[str] = Field(None, pattern="^(low|medium|high)$")

class PatientResponse(BaseModel):
    patient_id: str
    name: str
    birthDate: str
    height: str  # Changed to str to handle existing data
    weight: str  # Changed to str to handle existing data
    lab_results: Dict
    doctors_notes: str
    severity: str
    lab_results_history: Optional[List[Dict]] = []
    doctors_notes_history: Optional[List[Dict]] = []

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

router = APIRouter(prefix="/patients")


@router.post("/", response_model=Dict)
async def create_patient(patient: PatientCreate):
    try:
        height = float(patient.height) if patient.height is not None else 0.0
    except ValueError:
        height = 0.0
    try:
        weight = float(patient.weight) if patient.weight is not None else 0.0
    except ValueError:
        weight = 0.0

    lab_results = patient.lab_results if patient.lab_results is not None else {}
    doctors_notes = patient.doctors_notes if patient.doctors_notes is not None else ""
    result = await async_create_patient(
        name=patient.name,
        birthDate=patient.birthDate,
        height=height,
        weight=weight,
        lab_results=lab_results,
        doctors_notes=doctors_notes,
        severity=patient.severity
    )

    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create patient"))

    return result

@router.get("/", response_model=PatientsListResponse)
async def get_patients(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000)
):
    return await async_get_all_patients_info(skip, limit)

@router.get("/{patient_id}", response_model=Dict)
async def get_patient(patient_id: str):
    result = await async_get_patient_info(patient_id)

    if not result.get("success", False):
        raise HTTPException(status_code=404, detail="Patient not found")

    return result

@router.put("/{patient_id}", response_model=Dict)
async def update_patient(patient_id: str, patient_update: PatientUpdate):
    update_data = {k: v for k, v in patient_update.dict().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid update data provided")

    result = await async_update_patient_info(patient_id, update_data)

    if not result.get("success", False):
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
