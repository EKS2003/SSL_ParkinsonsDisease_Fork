from fastapi import APIRouter, Depends, Query
from typing import Dict

from core.dependencies import get_patient_service, get_current_user
from routes.contracts import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientsListResponse,
    PatientSearchResponse,
    FilterCriteria,
)
from repo.sql_models import User
from services.patient_service import PatientService

router = APIRouter(prefix="/patients")


@router.post("/", response_model=Dict)
async def create_patient(
    patient: PatientCreate,
    service: PatientService = Depends(get_patient_service),
    current_user: User = Depends(get_current_user),
):
    patient_id = service.create_patient(user_id=current_user.id, data=patient)
    return {"patient_id": patient_id}


@router.get("/", response_model=PatientsListResponse)
async def get_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: PatientService = Depends(get_patient_service),
):
    return service.list_patients(skip, limit)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
):
    return service.get_patient(patient_id)


@router.put("/{patient_id}", response_model=Dict)
async def update_patient(
    patient_id: str,
    patient_update: PatientUpdate,
    service: PatientService = Depends(get_patient_service),
):
    service.update_patient(patient_id, patient_update)
    return {"patient_id": patient_id}


@router.delete("/{patient_id}", response_model=Dict)
async def delete_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
):
    service.delete_patient(patient_id)
    return {"patient_id": patient_id}


@router.get("/search/{query}", response_model=PatientSearchResponse)
async def search_patients(
    query: str,
    service: PatientService = Depends(get_patient_service),
):
    patients = service.search_patients(query)
    return {"patients": patients, "count": len(patients)}


@router.post("/filter/", response_model=PatientSearchResponse)
async def filter_patients(
    criteria: FilterCriteria,
    service: PatientService = Depends(get_patient_service),
):
    patients = service.filter_patients(criteria.model_dump(exclude_none=True))
    return {"patients": patients, "count": len(patients)}
