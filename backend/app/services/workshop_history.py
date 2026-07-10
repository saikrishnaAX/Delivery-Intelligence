"""Workshop sprint history from sprint sheets and release moves."""

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models import (
    SprintSheet, SprintSheetRow, Ticket, TicketSectionMove, AsanaProject,
)
from app.services.org_service import OrgService, normalize_workshop_key


class WorkshopHistoryService:
    def __init__(self, db: Session, project_gid: str | None = None):
        self.db = db
        self.org = OrgService(db)
        self.project_id = None
        if project_gid:
            p = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
            if p:
                self.project_id = p.id

    def _workshop_from_row(self, row: SprintSheetRow) -> str | None:
        data = row.row_data or {}
        for key in ("workshop", "workshop_name", "customer", "garage"):
            val = data.get(key)
            if val and str(val).strip():
                return str(val).strip()
        if row.ticket and row.ticket.workshop_name:
            return row.ticket.workshop_name
        return None

    def get_sprint_history(self) -> list[dict]:
        q = (
            self.db.query(SprintSheetRow)
            .join(SprintSheet)
            .filter(SprintSheetRow.sheet_status == "released")
            .options(joinedload(SprintSheetRow.sheet), joinedload(SprintSheetRow.ticket))
        )
        if self.project_id:
            q = q.filter(SprintSheet.project_id == self.project_id)

        grouped: dict[tuple[str, str], dict] = {}
        for row in q.all():
            workshop = self._workshop_from_row(row)
            if not workshop:
                continue
            sprint_name = row.sheet.name if row.sheet else "Unknown"
            key = (normalize_workshop_key(workshop), sprint_name)
            if key not in grouped:
                ax_id = row.ticket.ax_id if row.ticket else None
                support = self.org.get_support_for_workshop(workshop, ax_id)
                grouped[key] = {
                    "workshop_name": workshop,
                    "sprint_name": sprint_name,
                    "issues_released": 0,
                    "support_person_name": support.name if support else None,
                    "support_person_email": support.email if support else None,
                    "release_date": None,
                    "sprint_sheet_id": row.sheet_id,
                    "tickets": [],
                }
            grouped[key]["issues_released"] += 1
            released_at = None
            if row.ticket and row.ticket.released_at:
                released_at = row.ticket.released_at
            elif row.ticket_id:
                move = (
                    self.db.query(TicketSectionMove)
                    .filter(TicketSectionMove.ticket_id == row.ticket_id)
                    .order_by(TicketSectionMove.moved_at.desc())
                    .first()
                )
                if move:
                    released_at = move.moved_at
            if released_at:
                cur = grouped[key]["release_date"]
                if not cur or released_at > (cur if isinstance(cur, datetime) else datetime.fromisoformat(str(cur))):
                    grouped[key]["release_date"] = released_at
            if row.ticket:
                grouped[key]["tickets"].append({
                    "id": row.ticket.id,
                    "title": row.ticket.title,
                    "asana_url": row.ticket.asana_url,
                })

        results = list(grouped.values())
        for r in results:
            if isinstance(r["release_date"], datetime):
                r["release_date"] = r["release_date"].isoformat()
        results.sort(key=lambda x: (x.get("release_date") or "", x["workshop_name"]), reverse=True)
        return results

    def get_history_detail(self, workshop_name: str, sprint_name: str) -> dict | None:
        for entry in self.get_sprint_history():
            if (
                normalize_workshop_key(entry["workshop_name"]) == normalize_workshop_key(workshop_name)
                and entry["sprint_name"] == sprint_name
            ):
                return entry
        return None
