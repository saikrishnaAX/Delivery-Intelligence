from app.database import SessionLocal
from app.models import AsanaProject, Ticket

db = SessionLocal()
project = db.query(AsanaProject).filter(AsanaProject.gid == "1211199289980978").first()
tickets = (
    db.query(Ticket)
    .filter(Ticket.project_id == project.id, Ticket.removed_from_asana.is_(False))
    .all()
)
prioritized = [
    t for t in tickets
    if t.module and "priorit" in (t.module.name or "").lower()
]
prioritized.sort(key=lambda t: (t.asana_board_index if t.asana_board_index is not None else 9999, t.id))
print("Prioritized count:", len(prioritized))
print("Top 10:")
for i, t in enumerate(prioritized[:10]):
    pri = t.asana_priority_raw or "-"
    print(f"  {i + 1}. [{pri}] {(t.title or '')[:65]}")
db.close()
