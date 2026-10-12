from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.engineering_service import EngineeringService

router = APIRouter(prefix="/api/engineering", tags=["Engineering"])
service = EngineeringService()


@router.get("/summary")
def get_engineering_summary(db: Session = Depends(get_db)):
    try:
        return service.summary(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Engineering summary unavailable: {exc}") from exc


@router.get("/health")
def get_engineering_health(db: Session = Depends(get_db)):
    try:
        return service.health(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Engineering health unavailable: {exc}") from exc


@router.get("/diagnostics")
def get_engineering_diagnostics(db: Session = Depends(get_db)):
    try:
        return {"items": service.diagnostics(db)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Engineering diagnostics unavailable: {exc}") from exc


@router.get("/repositories")
def get_engineering_repositories(
    search: str | None = None,
    sort_by: str = Query("total_pull_requests", description="Field to sort by"),
    order: str = Query("desc", pattern="^(asc|desc|ASC|DESC)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return service.repositories(db, search=search, sort_by=sort_by, order=order, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Engineering repositories unavailable: {exc}") from exc


@router.get("/repository/{repo_id}")
def get_engineering_repository_detail(repo_id: str, db: Session = Depends(get_db)):
    try:
        detail = service.repository_detail(db, repo_id)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found in engineering analytics.")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Engineering repository detail unavailable: {exc}") from exc
