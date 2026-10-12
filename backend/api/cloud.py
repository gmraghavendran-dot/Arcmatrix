from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.cloud_service import CloudService

router = APIRouter(prefix="/api/cloud", tags=["Cloud"])
service = CloudService()


@router.get("/summary")
def get_cloud_summary(db: Session = Depends(get_db)):
    try:
        return service.summary(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cloud summary unavailable: {exc}") from exc


@router.get("/efficiency")
def get_cloud_efficiency(db: Session = Depends(get_db)):
    try:
        return service.efficiency(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cloud efficiency unavailable: {exc}") from exc


@router.get("/intelligence")
def get_cloud_intelligence(db: Session = Depends(get_db)):
    try:
        return service.cost_intelligence(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cloud intelligence unavailable: {exc}") from exc


@router.get("/providers")
def get_cloud_providers(db: Session = Depends(get_db)):
    try:
        return {"items": service.providers(db)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cloud providers unavailable: {exc}") from exc


@router.get("/services")
def get_cloud_services(
    provider: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return service.services(db, provider=provider, search=search, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cloud services unavailable: {exc}") from exc
