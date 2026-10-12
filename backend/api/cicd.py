from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.cicd_service import CicdService

router = APIRouter(prefix="/api/cicd", tags=["CI/CD"])
service = CicdService()


@router.get("/summary")
def get_cicd_summary(db: Session = Depends(get_db)):
    try:
        return service.summary(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"CI/CD summary unavailable: {exc}") from exc


@router.get("/health")
def get_cicd_health(db: Session = Depends(get_db)):
    try:
        return service.health(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"CI/CD health unavailable: {exc}") from exc


@router.get("/health-score")
def get_cicd_health_score(db: Session = Depends(get_db)):
    try:
        return service.pipeline_health_score(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"CI/CD health score unavailable: {exc}") from exc


@router.get("/repositories")
def get_cicd_repositories(
    search: str | None = None,
    sort_by: str = Query("total_runs", description="Field to sort by"),
    order: str = Query("desc", pattern="^(asc|desc|ASC|DESC)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return service.repositories(db, search=search, sort_by=sort_by, order=order, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"CI/CD repositories unavailable: {exc}") from exc


@router.get("/repository/{repo:path}")
def get_cicd_repository_detail(repo: str, db: Session = Depends(get_db)):
    try:
        detail = service.repository_detail(db, repo)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Repository '{repo}' not found in CI/CD analytics.")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"CI/CD repository detail unavailable: {exc}") from exc
