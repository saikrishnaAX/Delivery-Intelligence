"""Seed Support and Sales teams with production members."""

from __future__ import annotations

from app.database import SessionLocal
from app.services.org_service import OrgService

SUPPORT_TEAM = "Support"
SALES_TEAM = "Sales"

SUPPORT_MEMBERS: list[tuple[str, str]] = [
    ("Prasad", "prasad.r@autorox.co"),
    ("Basava Gadge", "cs.8@autorox.co"),
    ("Veeresh Kankatte", "cs.6@autorox.co"),
    ("Unnimaya", "cs.1@autorox.co"),
    ("Sigod Osman", "cs.17@autorox.co"),
    ("Kavya Mathangi", "cs.4@autorox.co"),
    ("Shashikala", "cs.11@autorox.co"),
    ("Afra", "cs.9@autorox.co"),
    ("Danya", "cs.5@autorox.co"),
    ("Rakesh Macha", "cs.7@autorox.co"),
    ("Vishnu", "cs.3@autorox.co"),
]

SALES_MEMBERS: list[tuple[str, str]] = [
    ("Ambica Rayane", "cc.7@autorox.co"),
    ("Manibabu Nagala", "cc.1@autorox.co"),
    ("Janitha Singaraju", "amal.r@autorox.co"),
    ("Thulasi Ram Gali", "ts.1@autorox.co"),
]


def main() -> None:
    db = SessionLocal()
    try:
        svc = OrgService(db)

        support = svc.upsert_team(
            SUPPORT_TEAM,
            description="Customer support agents for workshop assignments",
        )
        for name, email in SUPPORT_MEMBERS:
            person = svc.upsert_person(name, email)
            svc.add_team_member(support, person)

        sales = svc.upsert_team(
            SALES_TEAM,
            description="Sales and account management",
        )
        for name, email in SALES_MEMBERS:
            person = svc.upsert_person(name, email)
            svc.add_team_member(sales, person)

        db.commit()
        print(f"Support team: {len(SUPPORT_MEMBERS)} members")
        print(f"Sales team: {len(SALES_MEMBERS)} members")
    finally:
        db.close()


if __name__ == "__main__":
    main()
