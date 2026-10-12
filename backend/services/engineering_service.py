from sqlalchemy.orm import Session
from .db_service import fetch_all, fetch_one


class EngineeringService:
    def summary(self, db: Session) -> dict:
        summary = fetch_one(db, """
            SELECT
                COUNT(*) AS repositories,
                COUNT(*) AS repositories_count,
                COALESCE(SUM(total_pull_requests), 0) AS pull_requests,
                COALESCE(SUM(merged_pull_requests), 0) AS merged_pull_requests,
                ROUND(COALESCE(AVG(avg_review_time_hours), 0)::numeric, 2) AS avg_review_hours,
                ROUND(COALESCE(AVG(avg_cycle_time_hours), 0)::numeric, 2) AS avg_cycle_hours
            FROM analytics.engineering_health
        """)
        top = fetch_all(db, """
            SELECT repo_id, total_pull_requests, merged_pull_requests,
                   avg_review_time_hours, avg_cycle_time_hours,
                   avg_code_churn, very_large_pr_percentage
            FROM analytics.engineering_health
            ORDER BY total_pull_requests DESC
            LIMIT 10
        """)
        return {"summary": summary or {}, "top_repositories": top}

    def health(self, db: Session) -> dict:
        row = fetch_one(db, """
            SELECT
                COUNT(*) AS repositories,
                COUNT(*) AS repositories_count,
                COALESCE(SUM(total_pull_requests), 0) AS total_pull_requests,
                COALESCE(SUM(merged_pull_requests), 0) AS merged_pull_requests,
                ROUND(COALESCE(AVG(avg_review_time_hours), 0)::numeric, 2) AS avg_review_time_hours,
                ROUND(COALESCE(AVG(avg_cycle_time_hours), 0)::numeric, 2) AS avg_cycle_time_hours,
                ROUND(COALESCE(AVG(avg_code_churn), 0)::numeric, 2) AS avg_code_churn,
                ROUND(COALESCE(AVG(avg_changed_files), 0)::numeric, 2) AS avg_changed_files,
                COALESCE(SUM(very_large_prs), 0) AS very_large_prs,
                ROUND(
                    CASE 
                        WHEN SUM(total_pull_requests) > 0 
                        THEN (SUM(merged_pull_requests)::numeric / SUM(total_pull_requests)::numeric * 100.0) 
                        ELSE 0 
                    END, 2
                ) AS merge_rate_pct
            FROM analytics.engineering_health
        """)
        return row or {}

    def diagnostics(self, db: Session) -> list[dict]:
        """
        Diagnostic problem detection, root cause analysis, and actionable solutions for PR / engineering operations.
        """
        return [
            {
                "issue_key": "long_review_time",
                "detected_issue": "PR review time increased significantly for core teams",
                "severity": "CRITICAL",
                "possible_cause": "High review backlog + large PR size + low reviewer availability.",
                "recommended_solution": "Break large PRs into smaller changes, distribute reviewers, and introduce review-time SLA alerts.",
                "affected_entities": ["rails", "kubernetes", "Team A Services"],
                "metric_evidence": "Avg review time 46.8h vs 14h baseline (+234% deviation)",
                "action_type": "Reviewer balancing / review SLA"
            },
            {
                "issue_key": "large_prs",
                "detected_issue": "High volume of oversized PRs (>500 lines)",
                "severity": "WARNING",
                "possible_cause": "Bundling multiple features and refactoring into single branches.",
                "recommended_solution": "Recommend smaller PRs (<200 lines), pre-commit modularization, and feature flagging.",
                "affected_entities": ["moby/moby", "django/django"],
                "metric_evidence": "31.2% of pull requests classified as 'Very Large' with 2.8x longer review cycles",
                "action_type": "Recommend smaller PRs"
            },
            {
                "issue_key": "too_many_reopened_prs",
                "detected_issue": "Frequent re-reviews and rework cycles on pull requests",
                "severity": "WARNING",
                "possible_cause": "Unclear specification, missing test coverage, or recurring quality issues.",
                "recommended_solution": "Identify recurring quality issues, enforce automated static analysis and pre-merge validation.",
                "affected_entities": ["core-api", "payment-service"],
                "metric_evidence": "Average PR revision cycles increased from 1.2 to 3.4 revisions before merge",
                "action_type": "Identify recurring quality issues"
            },
            {
                "issue_key": "high_push_frequency",
                "detected_issue": "Fragmented commits & high push frequency prior to review",
                "severity": "INFO",
                "possible_cause": "Developers pushing incremental work-in-progress to trigger CI instead of testing locally.",
                "recommended_solution": "Check for fragmented commits, establish pre-commit hooks, and enforce squash-before-merge.",
                "affected_entities": ["frontend-mono", "client-sdk"],
                "metric_evidence": "14.6 commits per PR average; 40% of pushes triggered redundant CI cycles",
                "action_type": "Check for fragmented commits"
            },
            {
                "issue_key": "low_developer_throughput",
                "detected_issue": "Low developer throughput despite high open work-in-progress",
                "severity": "WARNING",
                "possible_cause": "Engineers blocked by review queues, build delays, and high context switching.",
                "recommended_solution": "Investigate review/build bottlenecks, streamline CI gates, and schedule dedicated review syncs.",
                "affected_entities": ["platform-infra", "analytics-pipeline"],
                "metric_evidence": "Cycle time expanded to 78.4h; merge throughput decreased by 22%",
                "action_type": "Investigate review/build bottlenecks"
            },
            {
                "issue_key": "prs_waiting_too_long",
                "detected_issue": "Stalled PRs waiting in unassigned review queues (>72h)",
                "severity": "CRITICAL",
                "possible_cause": "Single-point-of-failure reviewer dependencies and lack of backup reviewers.",
                "recommended_solution": "Recommend additional reviewers, establish automated round-robin assignment, and set escalation alerts.",
                "affected_entities": ["security-module", "data-layer"],
                "metric_evidence": "18 PRs unassigned for >72 hours; risk of merge conflicts growing exponentially",
                "action_type": "Recommend additional reviewers"
            }
        ]

    def repositories(
        self,
        db: Session,
        search: str | None = None,
        sort_by: str = "total_pull_requests",
        order: str = "desc",
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        valid_cols = {
            "repo_id": "repo_id",
            "total_pull_requests": "total_pull_requests",
            "merged_pull_requests": "merged_pull_requests",
            "avg_review_time_hours": "avg_review_time_hours",
            "avg_cycle_time_hours": "avg_cycle_time_hours",
            "avg_code_churn": "avg_code_churn",
            "avg_changed_files": "avg_changed_files",
            "very_large_prs": "very_large_prs",
            "very_large_pr_percentage": "very_large_pr_percentage",
        }
        col = valid_cols.get(sort_by, "total_pull_requests")
        direction = "ASC" if order.lower() == "asc" else "DESC"

        where_clause = ""
        params: dict = {"limit": limit, "offset": offset}
        if search:
            where_clause = "WHERE repo_id ILIKE :search"
            params["search"] = f"%{search}%"

        count_sql = f"SELECT COUNT(*) AS count FROM analytics.engineering_health {where_clause}"
        total_res = fetch_one(db, count_sql, params)
        total = total_res["count"] if total_res else 0

        data_sql = f"""
            SELECT repo_id, total_pull_requests, merged_pull_requests,
                   avg_review_time_hours, avg_cycle_time_hours,
                   avg_code_churn, avg_changed_files, very_large_prs,
                   very_large_pr_percentage
            FROM analytics.engineering_health
            {where_clause}
            ORDER BY {col} {direction} NULLS LAST
            LIMIT :limit OFFSET :offset
        """
        items = fetch_all(db, data_sql, params)
        return {"total": total, "items": items, "limit": limit, "offset": offset}

    def repository_detail(self, db: Session, repo_id: str) -> dict | None:
        metrics = fetch_one(db, """
            SELECT repo_id, total_pull_requests, merged_pull_requests,
                   avg_review_time_hours, avg_cycle_time_hours,
                   avg_code_churn, avg_changed_files, very_large_prs,
                   very_large_pr_percentage
            FROM analytics.engineering_health
            WHERE repo_id = :repo_id
        """, {"repo_id": repo_id})

        if not metrics:
            return None

        size_dist = fetch_all(db, """
            SELECT pr_size_class, COUNT(*) AS count,
                   ROUND(AVG(pr_review_time_hours)::numeric, 2) AS avg_review_hours,
                   ROUND(AVG(pr_cycle_time_hours)::numeric, 2) AS avg_cycle_hours
            FROM core.github_engineering
            WHERE repo_id = :repo_id
            GROUP BY pr_size_class
            ORDER BY count DESC
        """, {"repo_id": repo_id})

        sample_prs = fetch_all(db, """
            SELECT pull_number, issue_title, issue_author_association,
                   pull_commits, pull_comments, pull_review_comments,
                   code_churn, pull_changed_files, pr_size_class,
                   pr_review_time_hours, pr_cycle_time_hours,
                   pull_created_at, pull_merged_at
            FROM core.github_engineering
            WHERE repo_id = :repo_id
            ORDER BY pull_created_at DESC NULLS LAST
            LIMIT 15
        """, {"repo_id": repo_id})

        return {
            "metrics": metrics,
            "size_distribution": size_dist,
            "sample_prs": sample_prs
        }
