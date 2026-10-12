from sqlalchemy.orm import Session
from .db_service import fetch_all, fetch_one


class AiService:
    def summary(self, db: Session) -> dict:
        summary = fetch_one(db, """
            SELECT
                COUNT(*) AS models,
                COALESCE(SUM(total_requests), 0) AS total_requests,
                COALESCE(SUM(error_requests), 0) AS error_requests,
                ROUND(COALESCE(AVG(success_rate_pct), 0)::numeric, 2) AS avg_success_rate_pct,
                ROUND(COALESCE(AVG(avg_latency_ms), 0)::numeric, 2) AS avg_latency_ms,
                ROUND(COALESCE(AVG(avg_ttft_ms), 0)::numeric, 2) AS avg_ttft_ms,
                ROUND(COALESCE(AVG(avg_tokens_per_sec), 0)::numeric, 2) AS avg_tokens_per_sec
            FROM analytics.ai_health
        """)
        top = fetch_all(db, """
            SELECT provider, model, total_requests, error_requests,
                   success_rate_pct, error_rate_pct,
                   avg_ttft_ms, avg_latency_ms, avg_tokens_per_sec
            FROM analytics.ai_health
            ORDER BY total_requests DESC
            LIMIT 12
        """)
        return {"summary": summary or {}, "top_models": top}

    def health(self, db: Session) -> dict:
        row = fetch_one(db, """
            SELECT
                COUNT(*) AS models,
                COUNT(*) AS models_count,
                COALESCE(SUM(total_requests), 0) AS total_requests,
                COALESCE(SUM(successful_requests), 0) AS successful_requests,
                COALESCE(SUM(error_requests), 0) AS error_requests,
                ROUND(COALESCE(AVG(success_rate_pct), 0)::numeric, 2) AS avg_success_rate_pct,
                ROUND(COALESCE(AVG(error_rate_pct), 0)::numeric, 2) AS avg_error_rate_pct,
                ROUND(COALESCE(AVG(avg_ttft_ms), 0)::numeric, 2) AS avg_ttft_ms,
                ROUND(COALESCE(AVG(avg_latency_ms), 0)::numeric, 2) AS avg_latency_ms,
                ROUND(COALESCE(AVG(avg_tokens_per_sec), 0)::numeric, 2) AS avg_tokens_per_sec,
                ROUND(COALESCE(AVG(avg_token_count), 0)::numeric, 2) AS avg_token_count
            FROM analytics.ai_health
        """)
        return row or {}

    def models(
        self,
        db: Session,
        provider: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        conditions = []
        params: dict = {"limit": limit, "offset": offset}

        if provider:
            conditions.append("provider = :provider")
            params["provider"] = provider
        if search:
            conditions.append("(model ILIKE :search OR provider ILIKE :search)")
            params["search"] = f"%{search}%"

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_sql = f"SELECT COUNT(*) AS count FROM analytics.ai_health {where_clause}"
        total_res = fetch_one(db, count_sql, params)
        total = total_res["count"] if total_res else 0

        data_sql = f"""
            SELECT provider, model, total_requests, successful_requests,
                   error_requests, success_rate_pct, error_rate_pct,
                   avg_ttft_ms, avg_latency_ms, avg_tokens_per_sec,
                   avg_token_count
            FROM analytics.ai_health
            {where_clause}
            ORDER BY total_requests DESC
            LIMIT :limit OFFSET :offset
        """
        items = fetch_all(db, data_sql, params)
        return {"total": total, "items": items, "limit": limit, "offset": offset}

    def model_detail(self, db: Session, model: str) -> dict | None:
        metrics = fetch_one(db, """
            SELECT provider, model, total_requests, successful_requests,
                   error_requests, success_rate_pct, error_rate_pct,
                   avg_ttft_ms, avg_latency_ms, avg_tokens_per_sec,
                   avg_token_count
            FROM analytics.ai_health
            WHERE model = :model
        """, {"model": model})

        if not metrics:
            return None

        status_breakdown = fetch_all(db, """
            SELECT status, COUNT(*) AS count,
                   ROUND(AVG(latency_ms)::numeric, 2) AS avg_latency_ms,
                   ROUND(AVG(ttft_ms)::numeric, 2) AS avg_ttft_ms,
                   ROUND(AVG(tokens_per_sec)::numeric, 2) AS avg_tokens_per_sec
            FROM core.ai_usage
            WHERE model = :model
            GROUP BY status
            ORDER BY count DESC
        """, {"model": model})

        recent_events = fetch_all(db, """
            SELECT status, ttft_ms, latency_ms, tokens_per_sec,
                   token_count, throughput_score, error, event_timestamp
            FROM core.ai_usage
            WHERE model = :model
            ORDER BY event_timestamp DESC NULLS LAST
            LIMIT 15
        """, {"model": model})

        return {
            "metrics": metrics,
            "status_breakdown": status_breakdown,
            "recent_events": recent_events
        }
