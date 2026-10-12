from sqlalchemy import text
from sqlalchemy.orm import Session
from .db_service import fetch_all, fetch_one


class PlatformService:
    def summary(self, db: Session) -> dict:
        eng_summary = fetch_one(db, """
            SELECT
                COUNT(*) AS repositories,
                COALESCE(SUM(total_pull_requests), 0) AS pull_requests,
                COALESCE(SUM(merged_pull_requests), 0) AS merged_pull_requests,
                ROUND(COALESCE(AVG(avg_review_time_hours), 0)::numeric, 2) AS avg_review_hours,
                ROUND(COALESCE(AVG(avg_cycle_time_hours), 0)::numeric, 2) AS avg_cycle_hours,
                ROUND(COALESCE(AVG(avg_code_churn), 0)::numeric, 2) AS avg_code_churn,
                COALESCE(SUM(very_large_prs), 0) AS very_large_prs
            FROM analytics.engineering_health
        """) or {}

        cicd_summary = fetch_one(db, """
            SELECT
                COUNT(*) AS repositories,
                COALESCE(SUM(total_runs), 0) AS total_runs,
                COALESCE(SUM(successful_runs), 0) AS successful_runs,
                COALESCE(SUM(failed_runs), 0) AS failed_runs,
                COALESCE(SUM(retried_runs), 0) AS retried_runs,
                ROUND(COALESCE(AVG(success_rate_pct), 0)::numeric, 2) AS avg_success_rate_pct,
                ROUND(COALESCE(AVG(failure_rate_pct), 0)::numeric, 2) AS avg_failure_rate_pct,
                ROUND(COALESCE(AVG(retry_rate_pct), 0)::numeric, 2) AS avg_retry_rate_pct,
                ROUND(COALESCE(AVG(avg_duration_seconds), 0)::numeric, 2) AS avg_duration_seconds
            FROM analytics.cicd_health
        """) or {}

        cloud_summary = fetch_one(db, """
            SELECT
                COUNT(*) AS service_regions,
                ROUND(COALESCE(SUM(total_billed_cost), 0)::numeric, 4) AS total_billed_cost,
                ROUND(COALESCE(SUM(total_effective_cost), 0)::numeric, 4) AS total_effective_cost,
                ROUND(COALESCE(SUM(total_cost_variance), 0)::numeric, 4) AS total_cost_variance,
                COALESCE(SUM(resources), 0) AS total_resources
            FROM analytics.cloud_efficiency
        """) or {}

        ai_summary = fetch_one(db, """
            SELECT
                COUNT(*) AS models,
                COALESCE(SUM(total_requests), 0) AS total_requests,
                COALESCE(SUM(successful_requests), 0) AS successful_requests,
                COALESCE(SUM(error_requests), 0) AS error_requests,
                ROUND(COALESCE(AVG(success_rate_pct), 0)::numeric, 2) AS avg_success_rate_pct,
                ROUND(COALESCE(AVG(error_rate_pct), 0)::numeric, 2) AS avg_error_rate_pct,
                ROUND(COALESCE(AVG(avg_latency_ms), 0)::numeric, 2) AS avg_latency_ms,
                ROUND(COALESCE(AVG(avg_ttft_ms), 0)::numeric, 2) AS avg_ttft_ms,
                ROUND(COALESCE(AVG(avg_tokens_per_sec), 0)::numeric, 2) AS avg_tokens_per_sec
            FROM analytics.ai_health
        """) or {}

        platform_health_rows = fetch_all(db, """
            SELECT domain, entities, metric_1, metric_2, metric_3
            FROM analytics.platform_health
            ORDER BY domain
        """)

        insight_counts = fetch_all(db, """
            SELECT domain, severity, COUNT(*) AS count
            FROM analytics.cross_domain_insights
            GROUP BY domain, severity
            ORDER BY domain, severity
        """)

        severity_totals = fetch_all(db, """
            SELECT severity, COUNT(*) AS count
            FROM analytics.cross_domain_insights
            GROUP BY severity
        """)
        severity_map = {row["severity"]: row["count"] for row in severity_totals}

        critical_insights = fetch_all(db, """
            SELECT insight_id, domain, severity, title,
                   description, entity_name, metric_name,
                   current_value, threshold_value,
                   deviation_percent, recommendation, created_at
            FROM analytics.cross_domain_insights
            WHERE severity = 'CRITICAL'
            ORDER BY ABS(COALESCE(deviation_percent, 0)) DESC
            LIMIT 10
        """)

        warnings = fetch_all(db, """
            SELECT insight_id, domain, severity, title,
                   description, entity_name, metric_name,
                   current_value, threshold_value,
                   deviation_percent, recommendation, created_at
            FROM analytics.cross_domain_insights
            WHERE severity = 'WARNING'
            ORDER BY ABS(COALESCE(deviation_percent, 0)) DESC
            LIMIT 10
        """)

        provenance = [
            {
                "domain": "Engineering (GitHub)",
                "period": "2012-11-30 → 2020-10-23",
                "records": 14384,
                "scope": "PR volume, review time, cycle time, code churn, PR sizing",
                "notes": "Normalized issue/PR engineering dataset. No time overlap with CI/CD or Cloud."
            },
            {
                "domain": "CI/CD (Delivery)",
                "period": "2025-01-06 → 2026-03-09",
                "records": 303079,
                "scope": "Workflow executions, pipeline success/failure/retry rates, duration",
                "notes": "Duration normalized from source ms to seconds. 654 repositories."
            },
            {
                "domain": "Cloud (FOCUS Billing)",
                "period": "2024-09-01",
                "records": 1000,
                "scope": "Billed & effective cost, cost variance, service-region concentration",
                "notes": "Standardized FOCUS billing sample. Surfaces observed cost concentration."
            },
            {
                "domain": "AI (LLM Telemetry)",
                "period": "2026-05-06 → 2026-08-23",
                "records": 39207,
                "scope": "TTFT, end-to-end latency, tokens/sec throughput, error rates",
                "notes": "Multi-provider LLM telemetry across 22 models."
            }
        ]

        return {
            "engineering": eng_summary,
            "cicd": cicd_summary,
            "cloud": cloud_summary,
            "ai": ai_summary,
            "platform_health_domains": platform_health_rows,
            "insight_counts": insight_counts,
            "critical_risks_count": severity_map.get("CRITICAL", 0),
            "warnings_count": severity_map.get("WARNING", 0),
            "info_count": severity_map.get("INFO", 0),
            "critical_risks": critical_insights,
            "warnings": warnings,
            "provenance": provenance
        }

    def health(self, db: Session) -> dict:
        checks = {}
        for table in (
            "analytics.platform_health",
            "analytics.engineering_health",
            "analytics.cicd_health",
            "analytics.cloud_efficiency",
            "analytics.ai_health",
            "analytics.cross_domain_insights",
        ):
            ok = db.execute(text(f"SELECT EXISTS (SELECT 1 FROM {table} LIMIT 1)")).scalar()
            checks[table] = bool(ok)
        return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
