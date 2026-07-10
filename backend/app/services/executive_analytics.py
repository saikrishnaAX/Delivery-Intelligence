"""Slim executive analytics — dashboard detail sections without full CEO intelligence payload."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ceo_intelligence import CEOIntelligenceService
from app.services.post_ai_issue_analysis import analyze_post_ai_issues


class ExecutiveAnalyticsService:
    """Builds only the fields used by ExecutiveAnalyticsView on the Execution tab."""

    def __init__(
        self,
        db: Session,
        project_gid: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        self._ceo = CEOIntelligenceService(db, project_gid, date_from, date_to)

    def build(self) -> dict[str, Any]:
        from datetime import timedelta

        windows = self._ceo._trend_windows()
        d30 = windows["last_30d"]
        releases_30 = d30.get("releases", {})
        health = self._ceo._health_score({"last_30d": d30, "recent_release": releases_30})
        ai_before, ai_after = self._ceo._ai_periods()
        recurring = self._ceo._top_recurring(10)
        monthly = self._ceo._monthly_series(9)
        post_ai_issue_nature = analyze_post_ai_issues(self._ceo.db, self._ceo.project_id)
        tickets_90 = self._ceo._tickets_in_range(self._ceo.now - timedelta(days=90), self._ceo.now)
        customer = self._ceo._customer_health(tickets_90)
        delivery = self._ceo._delivery_intel()

        return {
            "health_score": health,
            "quality_trends": {
                "windows": windows,
                "monthly": monthly,
                "bug_feature_ratio_30d": round(
                    d30["bugs"] / max(d30["enhancements"] + d30["requirements"], 1), 2
                ),
            },
            "ai_impact": {
                "before": ai_before,
                "after": ai_after,
                "adoption_date": self._ceo._ai_adoption_date().strftime("%Y-%m-%d"),
                "note": (
                    f"Pre-AI vs post-AI comparison from "
                    f"{self._ceo._ai_adoption_date().strftime('%d %B %Y')}; correlational, not causal."
                ),
            },
            "post_ai_issue_nature": post_ai_issue_nature,
            "recurring_issues": recurring,
            "engineering_productivity": {
                "last_30d": {
                    "enhancements": d30["enhancements"],
                    "bugs": d30["bugs"],
                    "closed": d30["closed"],
                    "reopened": d30["reopened"],
                    "blocked": d30["blocked"],
                    "avg_resolution_hours": d30["avg_resolution_hours"],
                },
            },
            "customer_health": customer,
            "delivery_intelligence": delivery,
            "charts": {
                "monthly_trends": monthly,
                "ai_comparison": [
                    {
                        "metric": "Tickets / month",
                        "before": ai_before.get("tickets_per_month"),
                        "after": ai_after.get("tickets_per_month"),
                    },
                    {
                        "metric": "Bugs / month",
                        "before": ai_before.get("bugs_per_month"),
                        "after": ai_after.get("bugs_per_month"),
                    },
                    {
                        "metric": "Enhancements / month",
                        "before": ai_before.get("enhancements_per_month"),
                        "after": ai_after.get("enhancements_per_month"),
                    },
                    {
                        "metric": "Bugs / release",
                        "before": ai_before.get("bugs_per_release"),
                        "after": ai_after.get("bugs_per_release"),
                    },
                    {
                        "metric": "Bug:Feature ratio",
                        "before": ai_before.get("bug_feature_ratio"),
                        "after": ai_after.get("bug_feature_ratio"),
                    },
                ],
            },
        }
