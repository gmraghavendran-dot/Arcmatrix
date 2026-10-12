from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_service import AiService

router = APIRouter(prefix="/api/ai", tags=["AI"])
service = AiService()


@router.get("/summary")
def get_ai_summary(db: Session = Depends(get_db)):
    try:
        return service.summary(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI summary unavailable: {exc}") from exc


@router.get("/health")
def get_ai_health(db: Session = Depends(get_db)):
    try:
        return service.health(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI health unavailable: {exc}") from exc


@router.get("/models")
def get_ai_models(
    provider: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return service.models(db, provider=provider, search=search, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI models unavailable: {exc}") from exc


@router.get("/model/{model:path}")
def get_ai_model_detail(model: str, db: Session = Depends(get_db)):
    try:
        detail = service.model_detail(db, model)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Model '{model}' not found in AI analytics.")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI model detail unavailable: {exc}") from exc
