"""Issue Intelligence — discover recurring product issues from ticket history."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta

from openai import OpenAI
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    AsanaProject,
    IssueIntelligenceJob,
    RecurringIssue,
    Ticket,
    TicketStatus,
)
from app.services.activity_log import log_activity
from app.services.engineering_fix_grouping import (
    compute_confidence,
    compute_severity,
    compute_trend,
    group_tickets_by_engineering_fix,
)
from app.services.ticket_parser import infer_module_affected

try:
    from app.services.cursor_analysis import cursor_available
except ImportError:
    def cursor_available() -> bool:
        return False

logger = logging.getLogger(__name__)
settings = get_settings()

STALE_JOB_SECONDS = 15 * 60
PROGRESS_CHUNK = 40

_analysis_locks: dict[int, threading.Lock] = {}
_analysis_lock_guard = threading.Lock()


def _project_analysis_lock(project_id: int) -> threading.Lock:
    with _analysis_lock_guard:
        if project_id not in _analysis_locks:
            _analysis_locks[project_id] = threading.Lock()
        return _analysis_locks[project_id]


def recover_orphaned_jobs(db: Session) -> int:
    """Mark in-flight jobs failed after server restart (daemon threads do not survive)."""
    orphaned = (
        db.query(IssueIntelligenceJob)
        .filter(IssueIntelligenceJob.status.in_(["pending", "running"]))
        .all()
    )
    if not orphaned:
        return 0
    now = datetime.utcnow()
    for job in orphaned:
        job.status = "failed"
        job.error_message = "Analysis interrupted — server restarted or job lost. Run again."
        job.completed_at = now
    db.commit()
    return len(orphaned)


class IssueIntelligenceService:
    def __init__(self, db: Session):
        self.db = db
        use_ai = settings.cluster_analysis_use_openai and bool(settings.openai_api_key)
        self._client = OpenAI(api_key=settings.openai_api_key) if use_ai else None

    def get_project(self, project_gid: str) -> AsanaProject | None:
        return self.db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()

    def recover_stale_jobs(self, project_id: int | None = None) -> None:
        stale = datetime.utcnow() - timedelta(seconds=STALE_JOB_SECONDS)
        q = self.db.query(IssueIntelligenceJob).filter(
            IssueIntelligenceJob.status.in_(["pending", "running"]),
        )
        if project_id:
            q = q.filter(IssueIntelligenceJob.project_id == project_id)
        for job in q.all():
            started = job.started_at or job.created_at
            if started and started < stale:
                job.status = "failed"
                job.error_message = "Analysis timed out"
                job.completed_at = datetime.utcnow()
        self.db.commit()

    def get_active_job(self, project_id: int) -> IssueIntelligenceJob | None:
        self.recover_stale_jobs(project_id)
        return (
            self.db.query(IssueIntelligenceJob)
            .filter(
                IssueIntelligenceJob.project_id == project_id,
                IssueIntelligenceJob.status.in_(["pending", "running"]),
            )
            .order_by(IssueIntelligenceJob.created_at.desc())
            .first()
        )

    def get_latest_completed_job(self, project_id: int) -> IssueIntelligenceJob | None:
        return (
            self.db.query(IssueIntelligenceJob)
            .filter(
                IssueIntelligenceJob.project_id == project_id,
                IssueIntelligenceJob.status == "completed",
            )
            .order_by(IssueIntelligenceJob.completed_at.desc())
            .first()
        )

    def get_job(self, job_id: int) -> IssueIntelligenceJob | None:
        job = self.db.query(IssueIntelligenceJob).filter(IssueIntelligenceJob.id == job_id).first()
        if job and job.status in ("pending", "running"):
            self.recover_stale_jobs(job.project_id)
            self.db.refresh(job)
        return job

    def load_project_tickets(self, project_id: int, date_from=None, date_to=None) -> list[Ticket]:
        q = (
            self.db.query(Ticket)
            .options(joinedload(Ticket.module))
            .filter(Ticket.project_id == project_id, Ticket.title.isnot(None))
        )
        if date_from:
            q = q.filter(Ticket.created_at >= date_from)
        if date_to:
            q = q.filter(Ticket.created_at <= date_to)
        return q.order_by(Ticket.created_at.desc()).all()

    def get_dashboard(self, project_gid: str, date_from=None, date_to=None) -> dict:
        project = self.get_project(project_gid)
        if not project:
            return self._empty_dashboard()

        self.recover_stale_jobs(project.id)
        active = self.get_active_job(project.id)
        latest = self.get_latest_completed_job(project.id)
        job_for_issues = latest

        issues: list[RecurringIssue] = []
        if job_for_issues:
            issues = (
                self.db.query(RecurringIssue)
                .filter(RecurringIssue.job_id == job_for_issues.id)
                .order_by(RecurringIssue.priority_score.desc())
                .all()
            )

        tickets = self.load_project_tickets(project.id, date_from, date_to)

        return {
            "tickets_analyzed": latest.tickets_total if latest else len(tickets),
            "recurring_issues_found": len(issues),
            "product_defects_found": len([i for i in issues if i.issue_type == "product_bug"]),
            "last_analyzed_at": latest.completed_at.isoformat() if latest and latest.completed_at else None,
            "active_job": self._job_summary(active) if active else None,
            "analysis_mode": latest.analysis_mode if latest else "engineering_fix (rule-based)",
            "issues": [self._issue_summary(i) for i in issues],
            "insights": self._dashboard_insights(issues, tickets),
        }

    def _empty_dashboard(self) -> dict:
        return {
            "tickets_analyzed": 0,
            "recurring_issues_found": 0,
            "product_defects_found": 0,
            "last_analyzed_at": None,
            "active_job": None,
            "analysis_mode": "engineering_fix (rule-based)",
            "issues": [],
            "insights": {},
        }

    def _job_summary(self, job: IssueIntelligenceJob) -> dict:
        return {
            "id": job.id,
            "status": job.status,
            "tickets_total": job.tickets_total,
            "tickets_processed": job.tickets_processed,
            "issues_found": job.issues_found,
            "error_message": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }

    def _issue_summary(self, issue: RecurringIssue) -> dict:
        intel = issue.intelligence or {}
        return {
            "id": issue.id,
            "issue_name": issue.issue_name,
            "issue_type": issue.issue_type,
            "severity": issue.severity,
            "ticket_count": issue.ticket_count,
            "open_count": issue.open_count,
            "workshop_count": issue.workshop_count,
            "trend": issue.trend,
            "confidence": issue.confidence,
            "priority_score": issue.priority_score,
            "recurring_since": issue.recurring_since,
            "latest_occurrence": issue.latest_occurrence,
            "affected_modules": issue.affected_modules or [],
            "affected_workshops": (issue.affected_workshops or [])[:5],
            "affected_releases": issue.affected_releases or [],
            "fix_status": intel.get("fix_status", "unknown"),
            "developer_resolution_available": intel.get("developer_resolution_available", False),
            "regression_tests_available": bool(intel.get("regression_test_cases")),
            "business_impact": intel.get("business_impact"),
            "customer_impact": intel.get("customer_impact"),
            "executive_summary": intel.get("executive_summary"),
        }

    def _dashboard_insights(self, issues: list[RecurringIssue], tickets: list[Ticket]) -> dict:
        increasing = [i for i in issues if i.trend == "increasing" and i.issue_type == "product_bug"]
        top_priority = sorted(issues, key=lambda x: x.priority_score, reverse=True)[:3]

        module_counts: dict[str, int] = {}
        for i in issues:
            if i.issue_type != "product_bug":
                continue
            for m in i.affected_modules or []:
                module_counts[m] = module_counts.get(m, 0) + i.open_count

        unstable = sorted(module_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "top_priority_issues": [i.issue_name for i in top_priority],
            "increasing_issues_count": len(increasing),
            "unstable_modules": [{"module": m, "open_tickets": c} for m, c in unstable],
            "tickets_in_range": len(tickets),
        }

    def get_issue_detail(self, issue_id: int) -> dict | None:
        issue = self.db.query(RecurringIssue).filter(RecurringIssue.id == issue_id).first()
        if not issue:
            return None

        intel = issue.intelligence or {}
        ticket_ids = issue.ticket_ids or []
        tickets = (
            self.db.query(Ticket)
            .filter(Ticket.id.in_(ticket_ids))
            .order_by(Ticket.created_at.desc())
            .all()
            if ticket_ids
            else []
        )

        evidence = [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "workshop_name": t.workshop_name,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "asana_url": t.asana_url,
                "description_excerpt": (t.description or "")[:300],
            }
            for t in tickets[:25]
        ]

        return {
            **self._issue_summary(issue),
            "engineering_fix_key": issue.engineering_fix_key,
            "engineering_fix_label": intel.get("engineering_fix_label"),
            "ticket_ids": ticket_ids,
            "overview": {
                "executive_summary": intel.get("executive_summary"),
                "issue_type": issue.issue_type,
                "engineering_fix_hypothesis": intel.get("engineering_fix_hypothesis"),
            },
            "evidence": evidence,
            "evidence_total": len(ticket_ids),
            "timeline": intel.get("timeline", []),
            "root_cause": intel.get("root_cause"),
            "developer_resolution": intel.get("developer_resolution_summary", "Resolution Unknown."),
            "business_impact": intel.get("business_impact"),
            "customer_impact": intel.get("customer_impact"),
            "related_issues": intel.get("related_issues", []),
            "regression_test_cases": intel.get("regression_test_cases", []),
            "suggested_permanent_fix": intel.get("suggested_permanent_fix"),
            "suggested_product_improvement": intel.get("suggested_product_improvement"),
            "release_version_introduced": intel.get("release_version_introduced"),
            "release_version_fixed": intel.get("release_version_fixed"),
            "sample_tickets": intel.get("top_customer_complaints", []),
            "all_workshops": issue.affected_workshops or [],
            "all_modules": issue.affected_modules or [],
            "all_releases": issue.affected_releases or [],
            "issue_history": intel.get("issue_history", []),
            "evidence_summary": intel.get("evidence_summary"),
            "confidence": issue.confidence,
        }

    def start_analysis(self, project_gid: str, date_from=None, date_to=None) -> IssueIntelligenceJob:
        project = self.get_project(project_gid)
        if not project:
            raise ValueError("Project not found")

        with _project_analysis_lock(project.id):
            self.recover_stale_jobs(project.id)
            active = self.get_active_job(project.id)
            if active:
                return active

            tickets = self.load_project_tickets(project.id, date_from, date_to)
            cap = settings.cluster_analysis_ticket_cap

            mode = "engineering_fix (rule-based)"
            if self._client:
                mode = "engineering_fix (rule-based; OpenAI used for regression tests only)"

            job = IssueIntelligenceJob(
                project_id=project.id,
                status="pending",
                tickets_total=min(len(tickets), cap),
                tickets_processed=0,
                analysis_mode=mode,
            )
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)

            ticket_ids = [t.id for t in tickets[:cap]]
            job_id = job.id

        def _run():
            from app.database import SessionLocal
            bg_db = SessionLocal()
            try:
                bg_svc = IssueIntelligenceService(bg_db)
                j = bg_svc.get_job(job_id)
                if j:
                    bg_svc._run_job(j, ticket_ids)
            except Exception as exc:
                logger.exception("Issue intelligence job failed")
                j = bg_db.query(IssueIntelligenceJob).filter(IssueIntelligenceJob.id == job_id).first()
                if j:
                    j.status = "failed"
                    j.error_message = str(exc)
                    j.completed_at = datetime.utcnow()
                    bg_db.commit()
            finally:
                bg_db.close()

        threading.Thread(target=_run, daemon=True).start()
        return job

    def run_analysis_sync(
        self,
        project_gid: str,
        date_from=None,
        date_to=None,
    ) -> IssueIntelligenceJob:
        """Synchronous analysis for scheduled Monday pipeline (no background thread)."""
        project = self.get_project(project_gid)
        if not project:
            raise ValueError("Project not found")

        with _project_analysis_lock(project.id):
            self.recover_stale_jobs(project.id)
            active = self.get_active_job(project.id)
            if active:
                return active

            tickets = self.load_project_tickets(project.id, date_from, date_to)
            cap = settings.cluster_analysis_ticket_cap
            mode = "engineering_fix (rule-based)"
            if cursor_available():
                mode = "engineering_fix + cursor weekly enrich"
            elif self._client:
                mode = "engineering_fix (rule-based; OpenAI used for regression tests only)"

            job = IssueIntelligenceJob(
                project_id=project.id,
                status="pending",
                tickets_total=min(len(tickets), cap),
                tickets_processed=0,
                analysis_mode=mode,
            )
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)

            ticket_ids = [t.id for t in tickets[:cap]]
            self._run_job(job, ticket_ids)
            self.db.refresh(job)
            return job

    def _run_job(self, job: IssueIntelligenceJob, ticket_ids: list[int]) -> None:
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.tickets_processed = 0
        self.db.commit()

        self.db.query(RecurringIssue).filter(RecurringIssue.project_id == job.project_id).delete(
            synchronize_session=False
        )
        self.db.flush()

        tickets = (
            self.db.query(Ticket)
            .filter(Ticket.id.in_(ticket_ids))
            .order_by(Ticket.created_at.desc())
            .all()
        )
        total = len(tickets)
        job.tickets_total = total
        job.tickets_processed = max(1, int(total * 0.1))
        self.db.commit()

        groups = group_tickets_by_engineering_fix(tickets)
        job.tickets_processed = max(1, int(total * 0.55))
        self.db.commit()

        if self._client and len(groups) > 1:
            groups = self._refine_groups_with_llm(groups)

        issues_created = 0
        group_count = max(len(groups), 1)
        for idx, group in enumerate(groups):
            group_tickets = group["tickets"]
            if not group_tickets:
                continue
            intel = self._build_intelligence(group, total)
            self._save_recurring_issue(job, group, intel)
            issues_created += 1
            job.issues_found = issues_created
            job.tickets_processed = min(
                total,
                int(total * (0.55 + 0.45 * (idx + 1) / group_count)),
            )
            self.db.commit()

        job.issues_found = issues_created
        job.tickets_processed = total
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        self.db.commit()

        log_activity(
            self.db,
            module="issue_intelligence",
            action="analyze_complete",
            summary=f"Found {issues_created} recurring issues from {len(tickets)} tickets",
            entity_type="project",
            entity_id=str(job.project_id),
            payload={"job_id": job.id, "issues_found": issues_created},
        )

    def _save_recurring_issue(self, job: IssueIntelligenceJob, group: dict, intel: dict) -> RecurringIssue:
        tickets: list[Ticket] = group["tickets"]
        open_count = sum(
            1 for t in tickets
            if t.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED)
        )
        workshops = list({
            (t.workshop_name or "").strip()
            for t in tickets
            if t.workshop_name and t.workshop_name.strip().lower() not in ("unknown", "—", "-", "n/a")
        })
        modules = list({infer_module_affected(t.title or "", t.description or "") for t in tickets})
        releases = list({r for t in tickets for r in [t.build_in, t.product_stage] if r})

        dates = [t.created_at for t in tickets if t.created_at]
        recurring_since = min(dates).strftime("%Y-%m-%d") if dates else None
        latest_dates = [t.updated_at or t.created_at for t in tickets if (t.updated_at or t.created_at)]
        latest = max(latest_dates).strftime("%Y-%m-%d") if latest_dates else None

        fix_key = group["engineering_fix_key"]
        trend = compute_trend(tickets)
        severity = compute_severity(open_count, len(workshops), group["issue_type"])
        confidence = compute_confidence(len(tickets), fix_key)
        priority = open_count * 3 + len(workshops) * 2 + (
            10 if severity == "critical" else 5 if severity == "high" else 0
        )

        issue = RecurringIssue(
            project_id=job.project_id,
            job_id=job.id,
            issue_name=group["issue_name"],
            engineering_fix_key=fix_key,
            issue_type=group["issue_type"],
            severity=severity,
            ticket_count=len(tickets),
            open_count=open_count,
            workshop_count=len(workshops),
            trend=trend,
            confidence=confidence,
            priority_score=priority,
            recurring_since=recurring_since,
            latest_occurrence=latest,
            ticket_ids=[t.id for t in tickets],
            affected_workshops=workshops,
            affected_modules=modules,
            affected_releases=releases,
            intelligence=intel,
        )
        self.db.add(issue)
        self.db.flush()
        return issue

    def _build_intelligence(self, group: dict, total_tickets: int) -> dict:
        tickets: list[Ticket] = group["tickets"]
        fix_label = group["engineering_fix_label"]
        share = len(tickets) / max(total_tickets, 1)

        open_count = sum(
            1 for t in tickets
            if t.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED)
        )
        workshops = list({
            (t.workshop_name or "").strip()
            for t in tickets
            if t.workshop_name and t.workshop_name.strip().lower() not in ("unknown", "—", "-", "n/a")
        })

        resolution = self._extract_resolution(tickets)
        has_resolution = resolution != "Resolution Unknown."
        fix_status = "fixed" if has_resolution else ("open" if open_count > 0 else "unknown")

        regression_tests: list[str] = []
        if has_resolution and self._client:
            regression_tests = self._generate_regression_tests(group, tickets, resolution)

        root_cause = self._infer_root_cause(group, resolution)
        complaints = [(t.title or "")[:120] for t in tickets[:8] if t.title]
        executive = (
            f"{group['issue_name']}: {len(tickets)} tickets across {len(workshops)} workshops. "
            f"Engineering would likely address this via {fix_label}. {open_count} still open."
        )

        dates = sorted(t.created_at for t in tickets if t.created_at)
        timeline = []
        if dates:
            by_month: dict[str, int] = {}
            for d in dates:
                key = d.strftime("%Y-%m")
                by_month[key] = by_month.get(key, 0) + 1
            timeline = [{"month": k, "count": v} for k, v in sorted(by_month.items())]

        return {
            "executive_summary": executive,
            "engineering_fix_label": fix_label,
            "engineering_fix_hypothesis": (
                f"A single engineering change in {fix_label} would likely resolve "
                f"{len(tickets)} related tickets."
            ),
            "root_cause": root_cause,
            "evidence_summary": (
                f"{len(tickets)} tickets merged because they share the same engineering fix area "
                f"({fix_label}), not just similar wording."
            ),
            "business_impact": (
                f"{open_count} open tickets blocking workshop operations across {len(workshops)} account(s)."
                if open_count
                else f"Historically affected {len(workshops)} workshop(s); currently no open tickets."
            ),
            "customer_impact": (
                f"Workshops reporting: {', '.join(complaints[:3])}"
                if complaints
                else "Multiple customer reports of the same underlying product problem."
            ),
            "fix_status": fix_status,
            "developer_resolution_available": has_resolution,
            "developer_resolution_summary": resolution,
            "regression_test_cases": regression_tests,
            "suggested_permanent_fix": self._suggest_fix(group),
            "suggested_product_improvement": (
                "Add validation and user-visible error when this failure mode occurs, "
                "so support tickets include actionable detail."
            ),
            "top_customer_complaints": complaints,
            "related_issues": [],
            "release_version_introduced": next((t.product_stage for t in tickets if t.product_stage), None),
            "release_version_fixed": next(
                (t.build_in for t in tickets if t.build_in and t.status == TicketStatus.CLOSED), None
            ),
            "timeline": timeline,
            "issue_history": [],
            "ticket_percentage": round(share * 100, 1),
        }

    def _extract_resolution(self, tickets: list[Ticket]) -> str:
        patterns = [
            r"fixed by", r"root cause", r"deployed", r"resolved by", r"patch",
            r"released in", r"fix applied", r"corrected in",
        ]
        for t in tickets:
            if t.status != TicketStatus.CLOSED:
                continue
            text = f"{t.title or ''} {t.description or ''}".lower()
            if any(re.search(p, text) for p in patterns):
                excerpt = (t.description or t.title or "")[:400]
                return excerpt.strip() or "Resolution Unknown."
        return "Resolution Unknown."

    def _infer_root_cause(self, group: dict, resolution: str) -> str:
        if resolution != "Resolution Unknown." and len(resolution.strip()) >= 30:
            return f"Documented resolution: {resolution[:200]}"
        return (
            f"Insufficient evidence — tickets cluster in {group['engineering_fix_label']}; "
            "no confirmed root cause in ticket text."
        )

    def _suggest_fix(self, group: dict) -> str:
        suggestions = {
            "gen:sequence": "Audit sequence/number generation; add idempotency and retry for failed allocations.",
            "render:pdf": "Inspect PDF template rendering and data binding for missing fields.",
            "integration:api": "Review API error handling, timeouts, and retry logic.",
            "calc:tax": "Validate tax calculation rules and rounding against GST requirements.",
            "auth:permission": "Review role-permission matrix for the affected workflow.",
        }
        return suggestions.get(
            group["engineering_fix_key"],
            f"Investigate and fix the underlying issue in {group['engineering_fix_label']}.",
        )

    def _sanitize_regression_tests(self, raw: object) -> list[str]:
        """Validate LLM regression test output — strings only, bounded length."""
        if not isinstance(raw, list):
            return []
        tests: list[str] = []
        for item in raw[:4]:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if len(text) < 10 or len(text) > 500:
                continue
            tests.append(text)
        return tests

    def _generate_regression_tests(self, group: dict, tickets: list[Ticket], resolution: str) -> list[str]:
        if resolution == "Resolution Unknown." or len(resolution.strip()) < 30:
            return []
        if not self._client:
            return []
        samples = [{"title": t.title, "description": (t.description or "")[:300]} for t in tickets[:5]]
        prompt = (
            "Generate 2-4 regression test cases ONLY because a verified resolution exists.\n\n"
            f"Issue: {group['issue_name']}\n"
            f"Engineering fix area: {group['engineering_fix_label']}\n"
            f"Resolution: {resolution}\n\n"
            f"Sample tickets:\n{json.dumps(samples)}\n\n"
            "Each test must reproduce the exact failure, then assert correct behavior after the fix.\n"
            "Return JSON array of strings."
        )
        try:
            resp = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.25,
            )
            raw = (resp.choices[0].message.content or "[]").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(raw)
            return self._sanitize_regression_tests(result)
        except Exception:
            logger.exception("Regression test generation failed")
        return []

    def _refine_groups_with_llm(self, groups: list[dict]) -> list[dict]:
        return groups
