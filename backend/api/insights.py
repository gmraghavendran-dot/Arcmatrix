from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.insight_service import InsightService

router = APIRouter(prefix="/api/insights", tags=["Insights"])
service = InsightService()


@router.get("")
@router.get("/")
def get_insights(
    domain: str | None = None,
    severity: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return service.list_insights(db, domain=domain, severity=severity, search=search, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Insights list unavailable: {exc}") from exc


@router.get("/summary")
def get_insights_summary(db: Session = Depends(get_db)):
    try:
        return service.summary(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Insights summary unavailable: {exc}") from exc


@router.get("/critical")
def get_critical_insights(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    try:
        return {"items": service.critical(db, limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Critical insights unavailable: {exc}") from exc


@router.get("/warnings")
def get_warning_insights(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    try:
        return {"items": service.warnings(db, limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Warning insights unavailable: {exc}") from exc


@router.get("/actions")
def get_action_center(db: Session = Depends(get_db)):
    try:
        return {"items": service.action_center(db)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Action center unavailable: {exc}") from exc


@router.get("/cross-domain")
def get_cross_domain_findings(db: Session = Depends(get_db)):
    try:
        return {"items": service.cross_domain_findings(db)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cross-domain findings unavailable: {exc}") from exc
