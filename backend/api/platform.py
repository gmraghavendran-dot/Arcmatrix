from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.platform_service import PlatformService

router = APIRouter(prefix="/api/platform", tags=["Platform"])
service = PlatformService()


@router.get("/summary")
def get_platform_summary(db: Session = Depends(get_db)):
    try:
        return service.summary(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Platform summary unavailable: {exc}") from exc


@router.get("/health")
def get_platform_health(db: Session = Depends(get_db)):
    try:
        return service.health(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Platform health unavailable: {exc}") from exc
