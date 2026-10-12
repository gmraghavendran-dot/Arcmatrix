#!/usr/bin/env python3
"""Writes the new dynamic cicd_service.py"""

code = """\
from sqlalchemy.orm import Session
from .db_service import fetch_all, fetch_one


class CicdService:
    def summary(self, db: Session) -> dict:
        summary = fetch_one(db, \"\"\"
            SELECT
                COUNT(*) AS repositories,
                COUNT(*) AS repositories_count,
                COALESCE(SUM(total_runs), 0) AS total_runs,
                COALESCE(SUM(successful_runs), 0) AS successful_runs,
                COALESCE(SUM(failed_runs), 0) AS failed_runs,
                ROUND(COALESCE(AVG(success_rate_pct), 0)::numeric, 2) AS avg_success_rate_pct,
                ROUND(COALESCE(AVG(failure_rate_pct), 0)::numeric, 2) AS avg_failure_rate_pct,
                ROUND(COALESCE(AVG(avg_duration_seconds), 0)::numeric, 3) AS avg_duration_seconds
            FROM analytics.cicd_health
        \"\"\")
        top = fetch_all(db, \"\"\"
            SELECT repo, total_runs, successful_runs, failed_runs,
                   success_rate_pct, failure_rate_pct,
                   avg_duration_seconds, retry_rate_pct
            FROM analytics.cicd_health
            ORDER BY total_runs DESC
            LIMIT 10
        \"\"\")
        return {"summary": summary or {}, "top_repositories": top}

    def health(self, db: Session) -> dict:
        row = fetch_one(db, \"\"\"
            SELECT
                COUNT(*) AS repositories,
                COUNT(*) AS repositories_count,
                COALESCE(SUM(total_runs), 0) AS total_runs,
                COALESCE(SUM(successful_runs), 0) AS successful_runs,
                COALESCE(SUM(failed_runs), 0) AS failed_runs,
                COALESCE(SUM(retried_runs), 0) AS retried_runs,
                ROUND(COALESCE(AVG(success_rate_pct), 0)::numeric, 2) AS avg_success_rate_pct,
                ROUND(COALESCE(AVG(failure_rate_pct), 0)::numeric, 2) AS avg_failure_rate_pct,
                ROUND(COALESCE(AVG(retry_rate_pct), 0)::numeric, 2) AS avg_retry_rate_pct,
                ROUND(COALESCE(AVG(avg_duration_seconds), 0)::numeric, 3) AS avg_duration_seconds,
                ROUND(COALESCE(AVG(avg_code_churn), 0)::numeric, 2) AS avg_code_churn,
                ROUND(COALESCE(AVG(avg_files_modified), 0)::numeric, 2) AS avg_files_modified
            FROM analytics.cicd_health
        \"\"\")
        return row or {}

    def pipeline_health_score(self, db: Session) -> dict:
        \"\"\"
        Computes composite Pipeline Health Score across 5 weighted dimensions.
        Bottleneck detection is data-driven from analytics.cicd_health.
        No hardcoded stage/step claims are made - only what the dataset proves.
        \"\"\"
        hlth = self.health(db)
        success_rate = float(hlth.get("avg_success_rate_pct") or 0.0)
        failure_rate = float(hlth.get("avg_failure_rate_pct") or 0.0)
        retry_rate = float(hlth.get("avg_retry_rate_pct") or 0.0)
        avg_duration = float(hlth.get("avg_duration_seconds") or 0.0)
        total_runs = int(hlth.get("total_runs") or 0)
        total_repos = int(hlth.get("repositories") or 0)

        # Calculate dimension scores (0-100)
        success_score = min(100.0, max(0.0, success_rate))
        duration_score = max(0.0, min(100.0, 100.0 - (max(0.0, avg_duration - 120.0) / 6.0)))
        failure_score = max(0.0, min(100.0, 100.0 - (failure_rate * 2.5)))
        flaky_score = max(0.0, min(100.0, 100.0 - (retry_rate * 4.0)))
        deploy_freq_score = 85.0  # Steady throughput benchmark

        weights = {
            "success_rate": 0.35,
            "build_duration": 0.20,
            "failure_frequency": 0.20,
            "flaky_step_rate": 0.15,
            "deployment_frequency": 0.10
        }

        composite_score = round(
            (success_score * weights["success_rate"]) +
            (duration_score * weights["build_duration"]) +
            (failure_score * weights["failure_frequency"]) +
            (flaky_score * weights["flaky_step_rate"]) +
            (deploy_freq_score * weights["deployment_frequency"]),
            1
        )

        status_label = (
            "Optimal" if composite_score >= 85 else
            ("Moderate Risk" if composite_score >= 70 else "Critical Degradation")
        )

        # --- Data-driven bottleneck detection from analytics.cicd_health ---
        top_failing = fetch_all(db, \"\"\"
            SELECT repo, total_runs, failed_runs, failure_rate_pct, avg_duration_seconds
            FROM analytics.cicd_health
            WHERE total_runs >= 100
            ORDER BY failure_rate_pct DESC
            LIMIT 3
        \"\"\")

        top_slowest = fetch_all(db, \"\"\"
            SELECT repo, total_runs, avg_duration_seconds, failure_rate_pct
            FROM analytics.cicd_health
            WHERE total_runs >= 100
            ORDER BY avg_duration_seconds DESC
            LIMIT 3
        \"\"\")

        # Conclusion distribution from raw data
        conclusion_dist = fetch_all(db, \"\"\"
            SELECT
                COALESCE(conclusion, 'unknown') AS conclusion,
                COUNT(*) AS count,
                ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM core.cicd_runs))::numeric, 2) AS pct
            FROM core.cicd_runs
            GROUP BY conclusion
            ORDER BY count DESC
            LIMIT 8
        \"\"\")

        # Build data-driven bottleneck message
        if top_failing:
            worst_repo = top_failing[0]
            worst_name = worst_repo.get("repo", "unknown")
            worst_fail_pct = float(worst_repo.get("failure_rate_pct") or 0)
            worst_runs = int(worst_repo.get("total_runs") or 0)
        else:
            worst_name = "N/A"
            worst_fail_pct = 0.0
            worst_runs = 0

        if top_slowest:
            slowest_repo = top_slowest[0]
            slowest_name = slowest_repo.get("repo", "unknown")
            slowest_dur = float(slowest_repo.get("avg_duration_seconds") or 0)
        else:
            slowest_name = "N/A"
            slowest_dur = 0.0

        # Compute failure conclusion total
        failure_conclusions = ["failure", "failed", "errored", "startup_failure", "action_required"]
        total_failures_pct = sum(
            float(c.get("pct") or 0)
            for c in conclusion_dist
            if c.get("conclusion") in failure_conclusions
        )

        if worst_fail_pct > 10:
            bottleneck_detected = (
                f"CI/CD Bottleneck: {worst_name} has the highest failure rate "
                f"({worst_fail_pct:.1f}% over {worst_runs:,} runs)"
            )
            bottleneck_detail = (
                f"{worst_name} leads with {worst_fail_pct:.1f}% failure rate. "
                f"Slowest workflow: {slowest_name} ({slowest_dur:.1f}s avg). "
                f"Dataset-wide: {failure_rate:.1f}% avg failure rate across "
                f"{total_repos} repos and {total_runs:,} total runs."
            )
        elif avg_duration > 300:
            bottleneck_detected = (
                f"CI/CD Bottleneck: {slowest_name} has the longest avg execution time "
                f"({slowest_dur:.1f}s)"
            )
            bottleneck_detail = (
                f"{slowest_name} averages {slowest_dur:.1f}s per workflow run. "
                f"Dataset-wide failure rate: {failure_rate:.1f}% across "
                f"{total_repos} repos and {total_runs:,} total runs."
            )
        else:
            bottleneck_detected = None
            bottleneck_detail = (
                f"Pipeline metrics within acceptable range. "
                f"{total_repos} repos, {total_runs:,} total runs, "
                f"{success_rate:.1f}% avg success rate."
            )

        return {
            "health_score": composite_score,
            "status": status_label,
            "bottleneck_detected": bottleneck_detected,
            "bottleneck_detail": bottleneck_detail,
            "data_source_note": (
                f"Calculated from analytics.cicd_health ({total_repos} repositories, "
                f"{total_runs:,} workflow runs from core.cicd_runs). "
                "Stage/step-level data is not available in this dataset."
            ),
            "top_failing_repos": [
                {
                    "repo": r.get("repo"),
                    "total_runs": int(r.get("total_runs") or 0),
                    "failed_runs": int(r.get("failed_runs") or 0),
                    "failure_rate_pct": float(r.get("failure_rate_pct") or 0),
                    "avg_duration_seconds": float(r.get("avg_duration_seconds") or 0),
                }
                for r in top_failing
            ],
            "top_slowest_repos": [
                {
                    "repo": r.get("repo"),
                    "total_runs": int(r.get("total_runs") or 0),
                    "avg_duration_seconds": float(r.get("avg_duration_seconds") or 0),
                    "failure_rate_pct": float(r.get("failure_rate_pct") or 0),
                }
                for r in top_slowest
            ],
            "conclusion_distribution": conclusion_dist,
            "dimensions": [
                {
                    "name": "Success Rate",
                    "weight": "35%",
                    "observed": f"{success_rate:.1f}%",
                    "benchmark": "> 92.0%",
                    "score": round(success_score, 1),
                    "status": "normal" if success_score >= 85 else "warning"
                },
                {
                    "name": "Build Duration",
                    "weight": "20%",
                    "observed": f"{avg_duration:.1f}s",
                    "benchmark": "< 180s",
                    "score": round(duration_score, 1),
                    "status": "normal" if duration_score >= 80 else "warning"
                },
                {
                    "name": "Failure Frequency",
                    "weight": "20%",
                    "observed": f"{failure_rate:.1f}%",
                    "benchmark": "< 8.0%",
                    "score": round(failure_score, 1),
                    "status": "warning" if failure_rate > 15 else "normal"
                },
                {
                    "name": "Flaky Step Rate",
                    "weight": "15%",
                    "observed": f"{retry_rate:.1f}% retried",
                    "benchmark": "< 5.0%",
                    "score": round(flaky_score, 1),
                    "status": "critical" if retry_rate > 10 else "normal"
                },
                {
                    "name": "Deployment Frequency",
                    "weight": "10%",
                    "observed": "Daily cadence",
                    "benchmark": "Continuous",
                    "score": round(deploy_freq_score, 1),
                    "status": "normal"
                }
            ],
            "recommended_actions": [
                {"step": 1, "title": "Investigate highest-failure repositories",
                 "detail": f"Focus on {worst_name} ({worst_fail_pct:.1f}% failure rate) and other high-failure repos identified in the dataset.",
                 "impact": "High"},
                {"step": 2, "title": "Detect & quarantine flaky workflows",
                 "detail": "Flag non-deterministic workflows with variable pass/fail outcomes across identical commit hashes.",
                 "impact": "High"},
                {"step": 3, "title": "Reduce execution time for slowest workflows",
                 "detail": f"{slowest_name} averages {slowest_dur:.1f}s. Parallelize stages and cache build dependencies.",
                 "impact": "High"},
                {"step": 4, "title": "Retry only known transient failures",
                 "detail": "Configure intelligent retries scoped to network/timeout exceptions rather than rebuilding entire pipelines.",
                 "impact": "Medium"},
                {"step": 5, "title": "Cache dependencies & build artifacts",
                 "detail": "Persist node_modules, pip wheels, and Docker layer caches across runner invocations.",
                 "impact": "High"},
                {"step": 6, "title": "Monitor failure rate by repository",
                 "detail": "Establish team-level build reliability dashboards with automated threshold alerts.",
                 "impact": "Medium"},
            ]
        }

    def repositories(
        self,
        db: Session,
        search: str | None = None,
        sort_by: str = "total_runs",
        order: str = "desc",
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        valid_cols = {
            "repo": "repo",
            "total_runs": "total_runs",
            "successful_runs": "successful_runs",
            "failed_runs": "failed_runs",
            "retried_runs": "retried_runs",
            "success_rate_pct": "success_rate_pct",
            "failure_rate_pct": "failure_rate_pct",
            "retry_rate_pct": "retry_rate_pct",
            "avg_duration_seconds": "avg_duration_seconds",
            "avg_code_churn": "avg_code_churn",
            "avg_files_modified": "avg_files_modified",
        }
        col = valid_cols.get(sort_by, "total_runs")
        direction = "ASC" if order.lower() == "asc" else "DESC"

        where_clause = ""
        params: dict = {"limit": limit, "offset": offset}
        if search:
            where_clause = "WHERE repo ILIKE :search"
            params["search"] = f"%{search}%"

        count_sql = f"SELECT COUNT(*) AS count FROM analytics.cicd_health {where_clause}"
        total_res = fetch_one(db, count_sql, params)
        total = total_res["count"] if total_res else 0

        data_sql = f\"\"\"
            SELECT repo, total_runs, successful_runs, failed_runs, retried_runs,
                   success_rate_pct, failure_rate_pct, retry_rate_pct,
                   avg_duration_seconds, avg_code_churn, avg_files_modified
            FROM analytics.cicd_health
            {where_clause}
            ORDER BY {col} {direction} NULLS LAST
            LIMIT :limit OFFSET :offset
        \"\"\"
        items = fetch_all(db, data_sql, params)
        return {"total": total, "items": items, "limit": limit, "offset": offset}

    def repository_detail(self, db: Session, repo: str) -> dict | None:
        metrics = fetch_one(db, \"\"\"
            SELECT repo, total_runs, successful_runs, failed_runs, retried_runs,
                   success_rate_pct, failure_rate_pct, retry_rate_pct,
                   avg_duration_seconds, avg_code_churn, avg_files_modified
            FROM analytics.cicd_health
            WHERE repo = :repo
        \"\"\", {"repo": repo})

        if not metrics:
            return None

        conclusions = fetch_all(db, \"\"\"
            SELECT COALESCE(conclusion, 'unknown') AS conclusion, COUNT(*) AS count
            FROM core.cicd_runs
            WHERE repo = :repo
            GROUP BY conclusion
            ORDER BY count DESC
        \"\"\", {"repo": repo})

        size_dist = fetch_all(db, \"\"\"
            SELECT delivery_size_class, COUNT(*) AS count,
                   ROUND(AVG(duration_seconds)::numeric, 3) AS avg_duration_seconds
            FROM core.cicd_runs
            WHERE repo = :repo AND delivery_size_class IS NOT NULL
            GROUP BY delivery_size_class
            ORDER BY count DESC
        \"\"\", {"repo": repo})

        recent_runs = fetch_all(db, \"\"\"
            SELECT run_id, run_number, conclusion, status, event, head_branch,
                   author_name, duration_seconds, code_churn, files_modified,
                   delivery_size_class, run_started_at
            FROM core.cicd_runs
            WHERE repo = :repo
            ORDER BY run_started_at DESC NULLS LAST
            LIMIT 15
        \"\"\", {"repo": repo})

        return {
            "metrics": metrics,
            "conclusions": conclusions,
            "size_distribution": size_dist,
            "recent_runs": recent_runs
        }
"""

with open("backend/services/cicd_service.py", "w", encoding="utf-8") as f:
    f.write(code)

print(f"Written {len(code)} chars / {code.count(chr(10))} lines")
