"""Workshop email drafts — release announcements for workshops (human review before send)."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import CustomerAccount, WorkshopEmailDraft
from app.services.activity_log import log_activity
from app.services.email_service import EmailService
from app.db_utils import commit_with_retry

settings = get_settings()

CATEGORY_LABELS = {
    "enhancement": "New features & improvements",
    "performance": "Performance improvements",
    "bug": "Bugs resolved",
    "security": "Security enhancements",
}

SECTION_ORDER = ("enhancement", "security", "performance", "bug")


def support_email_for_account(account: CustomerAccount) -> str | None:
    if account.support_contact_email and account.support_contact_email.strip():
        return account.support_contact_email.strip().lower()
    if account.primary_support and account.primary_support.email:
        return account.primary_support.email.strip().lower()
    return None


def build_cc_list(support_email: str | None) -> list[str]:
    cc: list[str] = []
    if support_email:
        cc.append(support_email)
    head = settings.support_head_email.strip().lower()
    if head and head not in cc:
        cc.append(head)
    return cc


def _valid_email(email: str | None) -> bool:
    return bool(email and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def _item_story_lines(items: list[dict], *, is_bug: bool = False) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(items, start=1):
        title = (item.get("title") or "Update").strip()
        if is_bug:
            detail = (item.get("fix") or item.get("summary") or "").strip()
            lines.append(f"{idx}. {title} — {detail}" if detail else f"{idx}. {title}")
        else:
            benefit = (item.get("impact_benefit") or item.get("impact") or item.get("summary") or "").strip()
            whats_new = item.get("whats_new") or []
            step = whats_new[0].strip() if whats_new else benefit
            if step and step != title:
                lines.append(f"{idx}. {title} — {step}")
            else:
                lines.append(f"{idx}. {title}")
    return lines


def build_release_announcement_bodies(
    release_payload: dict,
    workshop_name: str,
    sprint_name: str,
) -> tuple[str, str, str]:
    """Return subject, plain text, and HTML for a workshop release announcement."""
    release_date = release_payload.get("release_date") or "this release"
    sections = release_payload.get("sections") or {}
    total = release_payload.get("total_items") or 0
    counts = {key: len(sections.get(key) or []) for key in SECTION_ORDER}
    active = [k for k in SECTION_ORDER if counts[k] > 0]

    subject = f"[Autorox] {sprint_name} release update — {release_date}"

    summary_parts = []
    if counts["enhancement"]:
        summary_parts.append(f"{counts['enhancement']} new improvement{'s' if counts['enhancement'] != 1 else ''}")
    if counts["bug"]:
        summary_parts.append(f"{counts['bug']} bug{'s' if counts['bug'] != 1 else ''} resolved")
    if counts["security"]:
        summary_parts.append(f"{counts['security']} security enhancement{'s' if counts['security'] != 1 else ''}")
    if counts["performance"]:
        summary_parts.append(f"{counts['performance']} performance improvement{'s' if counts['performance'] != 1 else ''}")
    summary_line = ", ".join(summary_parts) if summary_parts else f"{total} update{'s' if total != 1 else ''}"

    text_parts = [
        f"Dear {workshop_name} team,",
        "",
        f"We are pleased to share what went live in {sprint_name} ({release_date}).",
        "",
        "AT A GLANCE",
        f"• {summary_line}",
        "",
        "WHAT THIS MEANS FOR YOUR WORKSHOP",
        "The items below are now available in your Autorox environment. Each point is listed in the order we recommend reviewing them.",
        "",
    ]

    html_parts = [
        f"<p>Dear <strong>{workshop_name}</strong> team,</p>",
        f"<p>We are pleased to share what went live in <strong>{sprint_name}</strong> ({release_date}).</p>",
        "<h3 style=\"margin:16px 0 8px;font-size:15px;\">At a glance</h3>",
        f"<p>{summary_line}</p>",
        "<p><strong>What this means for your workshop</strong><br>"
        "The items below are now available in your Autorox environment.</p>",
    ]

    for key in SECTION_ORDER:
        items = sections.get(key) or []
        if not items:
            continue
        label = CATEGORY_LABELS[key]
        text_parts.extend(["", label.upper(), ""])
        html_parts.append(f"<h3 style=\"margin:20px 0 8px;font-size:14px;\">{label}</h3><ol>")
        for line in _item_story_lines(items, is_bug=(key == "bug")):
            text_parts.append(line)
            clean = line.split(". ", 1)
            if len(clean) == 2:
                html_parts.append(f"<li><strong>{clean[1].split(' — ')[0]}</strong>")
                if " — " in clean[1]:
                    html_parts.append(f" — {clean[1].split(' — ', 1)[1]}")
                html_parts.append("</li>")
            else:
                html_parts.append(f"<li>{line}</li>")
        html_parts.append("</ol>")

    text_parts.extend([
        "",
        "If you have questions about any item above, reply to this email or contact your Autorox support representative.",
        "",
        "Regards,",
        "Autorox Product & Delivery Team",
    ])
    html_parts.append(
        "<p style=\"margin-top:20px;\">If you have questions, reply to this email or contact your Autorox support representative.</p>"
        "<p>Regards,<br><strong>Autorox Product &amp; Delivery Team</strong></p>"
    )

    return subject, "\n".join(text_parts), "".join(html_parts)


class WorkshopEmailDraftService:
    def __init__(self, db: Session):
        self.db = db

    def create_release_announcement_drafts(
        self,
        *,
        project_id: int | None,
        release_payload: dict,
        sprint_name: str,
        audience: str = "all",
        workshop_ids: list[int] | None = None,
    ) -> dict:
        """Create one pending draft per workshop for a release announcement."""
        q = self.db.query(CustomerAccount).options(joinedload(CustomerAccount.primary_support))
        if workshop_ids:
            accounts = q.filter(CustomerAccount.id.in_(workshop_ids)).all()
        elif audience == "bosch":
            accounts = q.filter(CustomerAccount.tier == "bosch").all()
        elif audience == "standard":
            accounts = q.filter(CustomerAccount.tier != "bosch").all()
        else:
            accounts = q.all()

        batch_key = f"{sprint_name}|{release_payload.get('release_date')}|{audience}"
        created = skipped_no_email = 0
        draft_ids: list[int] = []

        for account in accounts:
            workshop_email = (account.workshop_email or "").strip().lower()
            if not _valid_email(workshop_email):
                skipped_no_email += 1
                continue

            existing = (
                self.db.query(WorkshopEmailDraft)
                .filter(
                    WorkshopEmailDraft.draft_type == "release_announcement",
                    WorkshopEmailDraft.status == "pending",
                    WorkshopEmailDraft.workshop_name == account.workshop_name,
                )
                .first()
            )
            if existing and (existing.ticket_snapshot or {}).get("batch_key") == batch_key:
                continue

            support_email = support_email_for_account(account)
            cc = build_cc_list(support_email)
            subject, body_text, body_html = build_release_announcement_bodies(
                release_payload, account.workshop_name, sprint_name
            )

            draft = WorkshopEmailDraft(
                ticket_id=None,
                project_id=project_id,
                draft_type="release_announcement",
                status="pending",
                workshop_name=account.workshop_name,
                to_emails=[workshop_email],
                cc_emails=cc,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                ticket_snapshot={
                    "batch_key": batch_key,
                    "sprint_name": sprint_name,
                    "release_date": release_payload.get("release_date"),
                    "customer_account_id": account.id,
                    "ax_id": account.ax_id,
                    "audience": audience,
                    "total_items": release_payload.get("total_items"),
                },
            )
            self.db.add(draft)
            self.db.flush()
            draft_ids.append(draft.id)
            created += 1

        if created:
            log_activity(
                self.db,
                module="workshop_emails",
                action="release_drafts_created",
                summary=f"Created {created} release announcement draft(s) for {audience} workshops",
                payload={"audience": audience, "created": created, "batch_key": batch_key},
            )
            commit_with_retry(self.db)

        return {
            "created": created,
            "skipped_no_email": skipped_no_email,
            "eligible": len(accounts),
            "draft_ids": draft_ids[:50],
        }

    def list_drafts(self, status: str | None = "pending", limit: int = 100) -> list[WorkshopEmailDraft]:
        q = (
            self.db.query(WorkshopEmailDraft)
            .filter(WorkshopEmailDraft.draft_type == "release_announcement")
            .order_by(WorkshopEmailDraft.created_at.desc())
        )
        if status:
            q = q.filter(WorkshopEmailDraft.status == status)
        return q.limit(limit).all()

    def get_draft(self, draft_id: int) -> WorkshopEmailDraft | None:
        return self.db.query(WorkshopEmailDraft).filter(WorkshopEmailDraft.id == draft_id).first()

    def update_draft(
        self,
        draft_id: int,
        *,
        subject: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        to_emails: list[str] | None = None,
        cc_emails: list[str] | None = None,
    ) -> WorkshopEmailDraft:
        draft = self.get_draft(draft_id)
        if not draft:
            raise ValueError("Draft not found")
        if draft.status != "pending":
            raise ValueError("Only pending drafts can be edited")
        if subject is not None:
            draft.subject = subject.strip()
        if body_text is not None:
            draft.body_text = body_text
        if body_html is not None:
            draft.body_html = body_html
        if to_emails is not None:
            draft.to_emails = to_emails
        if cc_emails is not None:
            draft.cc_emails = cc_emails
        commit_with_retry(self.db)
        self.db.refresh(draft)
        return draft

    def send_draft(self, draft_id: int) -> WorkshopEmailDraft:
        draft = self.get_draft(draft_id)
        if not draft:
            raise ValueError("Draft not found")
        if draft.status != "pending":
            raise ValueError("Draft is not pending")
        if not draft.to_emails:
            raise ValueError("No recipients on draft")

        EmailService().send_email(
            to_emails=draft.to_emails,
            subject=draft.subject,
            body_text=draft.body_text,
            body_html=draft.body_html or None,
            cc_emails=draft.cc_emails or None,
        )
        draft.status = "sent"
        draft.sent_at = datetime.utcnow()
        log_activity(
            self.db,
            module="workshop_emails",
            action="draft_sent",
            summary=f"Sent release announcement to {draft.workshop_name}",
            entity_type="workshop_email_draft",
            entity_id=str(draft.id),
        )
        commit_with_retry(self.db)
        self.db.refresh(draft)
        return draft

    def cancel_draft(self, draft_id: int) -> WorkshopEmailDraft:
        draft = self.get_draft(draft_id)
        if not draft:
            raise ValueError("Draft not found")
        if draft.status != "pending":
            raise ValueError("Only pending drafts can be cancelled")
        draft.status = "cancelled"
        draft.cancelled_at = datetime.utcnow()
        commit_with_retry(self.db)
        self.db.refresh(draft)
        return draft

    def pending_count(self, project_gid: str | None = None) -> int:
        q = self.db.query(WorkshopEmailDraft).filter(
            WorkshopEmailDraft.status == "pending",
            WorkshopEmailDraft.draft_type == "release_announcement",
        )
        if project_gid:
            from app.models import AsanaProject

            project = self.db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
            if project:
                q = q.filter(WorkshopEmailDraft.project_id == project.id)
        return q.count()

    def audience_preview_counts(self) -> dict:
        accounts = self.db.query(CustomerAccount).all()
        def with_email(rows: list[CustomerAccount]) -> int:
            return sum(1 for a in rows if _valid_email(a.workshop_email))

        all_rows = accounts
        bosch = [a for a in accounts if (a.tier or "").lower() == "bosch"]
        standard = [a for a in accounts if (a.tier or "").lower() != "bosch"]
        return {
            "all": {"total": len(all_rows), "with_email": with_email(all_rows)},
            "bosch": {"total": len(bosch), "with_email": with_email(bosch)},
            "standard": {"total": len(standard), "with_email": with_email(standard)},
        }
