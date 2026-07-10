"""Schedule and send workshop feedback reminders."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import ScheduledReminder, SprintSheet, SprintSheetRow, Person
from app.services.activity_log import log_activity
from app.services.email_service import EmailService
from app.services.workshop_history import WorkshopHistoryService


class ReminderService:
    def __init__(self, db: Session):
        self.db = db
        self.email = EmailService()

    def schedule_feedback_reminders_for_sprint(
        self, sprint_sheet_id: int, release_date: datetime | None = None
    ) -> list[ScheduledReminder]:
        sheet = (
            self.db.query(SprintSheet)
            .filter(SprintSheet.id == sprint_sheet_id)
            .first()
        )
        if not sheet:
            return []

        history_svc = WorkshopHistoryService(self.db)
        due_base = release_date or datetime.utcnow()
        due_at = due_base + timedelta(days=7)
        created: list[ScheduledReminder] = []

        workshops: dict[str, int] = {}
        rows = (
            self.db.query(SprintSheetRow)
            .filter(
                SprintSheetRow.sheet_id == sprint_sheet_id,
                SprintSheetRow.sheet_status == "released",
            )
            .options(joinedload(SprintSheetRow.ticket))
            .all()
        )
        for row in rows:
            w = history_svc._workshop_from_row(row)
            if w:
                workshops[w] = workshops.get(w, 0) + 1

        from app.services.org_service import OrgService
        org = OrgService(self.db)

        for workshop_name, count in workshops.items():
            support = org.get_support_for_workshop(workshop_name)
            if not support:
                continue
            existing = (
                self.db.query(ScheduledReminder)
                .filter(
                    ScheduledReminder.sprint_sheet_id == sprint_sheet_id,
                    ScheduledReminder.workshop_name == workshop_name,
                    ScheduledReminder.status == "pending",
                )
                .first()
            )
            if existing:
                continue
            reminder = ScheduledReminder(
                reminder_type="workshop_feedback",
                workshop_name=workshop_name,
                sprint_sheet_id=sprint_sheet_id,
                support_person_id=support.id,
                due_at=due_at,
                status="pending",
                meta_data={"item_count": count, "sprint_name": sheet.name},
            )
            self.db.add(reminder)
            created.append(reminder)

        if created:
            log_activity(
                self.db,
                module="workshops",
                action="reminder_scheduled",
                summary=f"Scheduled {len(created)} feedback reminder(s) for {sheet.name}",
                entity_type="sprint_sheet",
                entity_id=str(sprint_sheet_id),
                payload={"count": len(created), "due_at": due_at.isoformat()},
            )
        self.db.commit()
        return created

    def process_due_reminders(self) -> list[dict]:
        now = datetime.utcnow()
        due = (
            self.db.query(ScheduledReminder)
            .filter(
                ScheduledReminder.status == "pending",
                ScheduledReminder.due_at <= now,
            )
            .options(joinedload(ScheduledReminder.support_person), joinedload(ScheduledReminder.sprint_sheet))
            .all()
        )
        results: list[dict] = []
        for reminder in due:
            person = reminder.support_person
            if not person or not person.email:
                reminder.status = "cancelled"
                results.append({"id": reminder.id, "status": "cancelled", "reason": "no email"})
                continue
            if not self.email.configured:
                results.append({"id": reminder.id, "status": "skipped", "reason": "email not configured"})
                continue
            sprint_name = (reminder.meta_data or {}).get("sprint_name") or (
                reminder.sprint_sheet.name if reminder.sprint_sheet else "Sprint"
            )
            item_count = (reminder.meta_data or {}).get("item_count", 0)
            text, html = self.email.workshop_feedback_body(
                reminder.workshop_name, sprint_name, item_count
            )
            subject = f"Feedback request: {reminder.workshop_name} — {sprint_name}"
            try:
                self.email.send_email([person.email], subject, text, html)
                reminder.status = "sent"
                reminder.sent_at = now
                entry = log_activity(
                    self.db,
                    module="workshops",
                    action="email_sent",
                    summary=f"Sent feedback reminder to {person.name} for {reminder.workshop_name}",
                    entity_type="scheduled_reminder",
                    entity_id=str(reminder.id),
                    payload={
                        "workshop": reminder.workshop_name,
                        "sprint": sprint_name,
                        "recipient": person.email,
                    },
                )
                reminder.activity_log_id = entry.id
                results.append({"id": reminder.id, "status": "sent", "to": person.email})
            except Exception as exc:
                results.append({"id": reminder.id, "status": "failed", "error": str(exc)})
        self.db.commit()
        return results

    def list_reminders(self, status: str | None = None) -> list[ScheduledReminder]:
        q = self.db.query(ScheduledReminder).options(
            joinedload(ScheduledReminder.support_person),
            joinedload(ScheduledReminder.sprint_sheet),
        )
        if status:
            q = q.filter(ScheduledReminder.status == status)
        return q.order_by(ScheduledReminder.due_at.desc()).limit(200).all()
