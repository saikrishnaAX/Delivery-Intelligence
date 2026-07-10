"""Teams, people, and customer account management with CSV import."""

import csv
import io
import re
from sqlalchemy.orm import Session, joinedload

from app.models import Team, Person, TeamMembership, CustomerAccount, CustomerSupportHistory
from app.services.activity_log import log_activity
from app.db_utils import commit_with_retry


def normalize_workshop_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def normalize_ax_id(ax_id: str | None) -> str:
    if not ax_id:
        return ""
    return re.sub(r"\s+", "", ax_id.strip().upper())


UNKNOWN_WORKSHOP_NAMES = {"", "unknown", "—", "-", "n/a", "na"}


def find_customer_account(
    db: Session,
    workshop_name: str | None = None,
    ax_id: str | None = None,
) -> CustomerAccount | None:
    """Resolve a workshop account — AX ID first (stable key), then workshop name."""
    ax_key = normalize_ax_id(ax_id)
    if ax_key:
        account = (
            db.query(CustomerAccount)
            .options(joinedload(CustomerAccount.primary_support))
            .filter(CustomerAccount.ax_id == ax_key)
            .first()
        )
        if account:
            return account
        for row in (
            db.query(CustomerAccount)
            .options(joinedload(CustomerAccount.primary_support))
            .filter(CustomerAccount.ax_id.isnot(None), CustomerAccount.ax_id != "")
            .all()
        ):
            if normalize_ax_id(row.ax_id) == ax_key:
                return row

    if not workshop_name:
        return None
    key = normalize_workshop_key(workshop_name)
    if not key or key in UNKNOWN_WORKSHOP_NAMES:
        return None
    for account in db.query(CustomerAccount).options(
        joinedload(CustomerAccount.primary_support)
    ).all():
        if normalize_workshop_key(account.workshop_name) == key:
            return account
    return None


def agent_slug(agent: str) -> str:
    raw = (agent or "").strip()
    if not raw or raw.lower() in ("#n/a", "n/a", "0", "-", "na"):
        return ""
    first = re.split(r"[/,&]", raw)[0].strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", first).strip("-")
    return slug


def agent_display_name(agent: str) -> str:
    raw = (agent or "").strip()
    if not raw:
        return ""
    first = re.split(r"[/,&]", raw)[0].strip()
    return first.title() if first.islower() or first.isupper() else first


def map_corporate_tier(corporate_type: str) -> str:
    ct = (corporate_type or "").strip().lower()
    if ct == "bosch":
        return "bosch"
    return "standard"


# CSV agent labels that should resolve to a different Support team first name.
AGENT_NAME_ALIASES: dict[str, str] = {
    "aniketh": "aniket",
}


def normalize_agent_label(agent: str) -> str:
    """Map legacy CSV spellings to Support team roster names."""
    display = agent_display_name(agent)
    if not display:
        return agent
    first = _first_token(display).lower()
    alias = AGENT_NAME_ALIASES.get(first)
    if alias:
        return alias.title()
    return display


def _name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").strip().lower())


def _first_token(name: str) -> str:
    parts = re.split(r"\s+", (name or "").strip())
    return parts[0] if parts else ""


def agent_names_match(agent: str, person_name: str) -> bool:
    """Match CSV agent label (e.g. Kavya, Sashikala) to a team member name."""
    agent_norm = normalize_agent_label(agent).strip().lower()
    if not agent_norm or not person_name:
        return False
    person_first = _first_token(person_name).lower()
    person_full = person_name.strip().lower()
    if agent_norm == person_first or agent_norm == person_full:
        return True
    if person_first.startswith(agent_norm) or agent_norm.startswith(person_first):
        return min(len(person_first), len(agent_norm)) >= 4
    agent_key = _name_key(agent_norm)
    person_key = _name_key(person_first)
    if agent_key and person_key and agent_key == person_key:
        return True
    if len(agent_key) >= 5 and len(person_key) >= 5:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, agent_key, person_key).ratio() >= 0.88
    return False


class OrgService:
    TEAMS_CSV_TEMPLATE = "team_name,member_name,member_email,is_lead\nDelivery Team,Jane Doe,jane@example.com,true\n"
    CUSTOMERS_CSV_TEMPLATE = (
        "customer_name,workshop_name,support_person_email,tier,industry\n"
        "ABC Motors,ABC Motors Garage,jane@example.com,premium,Automotive\n"
    )

    def __init__(self, db: Session):
        self.db = db

    def list_teams(self) -> list[Team]:
        return (
            self.db.query(Team)
            .options(joinedload(Team.memberships).joinedload(TeamMembership.person))
            .order_by(Team.name)
            .all()
        )

    def list_people(self) -> list[Person]:
        return self.db.query(Person).order_by(Person.name).all()

    def list_customer_accounts(self) -> list[CustomerAccount]:
        return (
            self.db.query(CustomerAccount)
            .options(joinedload(CustomerAccount.primary_support))
            .order_by(CustomerAccount.workshop_name)
            .all()
        )

    def get_person_by_email(self, email: str) -> Person | None:
        return self.db.query(Person).filter(Person.email == email.strip().lower()).first()

    def upsert_person(self, name: str, email: str, role: str | None = None) -> Person:
        email_norm = email.strip().lower()
        person = self.get_person_by_email(email_norm)
        if person:
            person.name = name.strip()
            if role:
                person.role = role
            person.is_active = True
        else:
            person = Person(name=name.strip(), email=email_norm, role=role)
            self.db.add(person)
            self.db.flush()
        return person

    def create_team(self, name: str, description: str | None = None) -> Team:
        existing = self.db.query(Team).filter(Team.name == name.strip()).first()
        if existing:
            raise ValueError(f"Team '{name}' already exists")
        team = Team(name=name.strip(), description=description)
        self.db.add(team)
        self.db.flush()
        log_activity(
            self.db,
            module="org",
            action="team_created",
            summary=f"Created team: {team.name}",
            entity_type="team",
            entity_id=str(team.id),
        )
        commit_with_retry(self.db)
        self.db.refresh(team)
        return team

    def update_team(self, team_id: int, name: str | None = None, description: str | None = None) -> Team:
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise ValueError("Team not found")
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Team name cannot be empty")
            clash = self.db.query(Team).filter(Team.name == name, Team.id != team_id).first()
            if clash:
                raise ValueError(f"Team '{name}' already exists")
            team.name = name
        if description is not None:
            team.description = description.strip() or None
        log_activity(
            self.db,
            module="org",
            action="team_updated",
            summary=f"Updated team: {team.name}",
            entity_type="team",
            entity_id=str(team.id),
        )
        commit_with_retry(self.db)
        self.db.refresh(team)
        return team

    def delete_team(self, team_id: int) -> None:
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise ValueError("Team not found")
        name = team.name
        self.db.delete(team)
        log_activity(
            self.db,
            module="org",
            action="team_deleted",
            summary=f"Deleted team: {name}",
            entity_type="team",
            entity_id=str(team_id),
        )
        commit_with_retry(self.db)

    def add_member_to_team(
        self,
        team_id: int,
        name: str,
        email: str,
        designation: str | None = None,
        is_lead: bool = False,
    ) -> TeamMembership:
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise ValueError("Team not found")
        person = self.upsert_person(name, email, role=designation)
        membership = self.add_team_member(team, person, is_lead=is_lead)
        log_activity(
            self.db,
            module="org",
            action="member_added",
            summary=f"Added {person.name} to {team.name}",
            entity_type="team",
            entity_id=str(team.id),
            payload={"email": person.email, "designation": designation},
        )
        commit_with_retry(self.db)
        return membership

    def update_team_member(
        self,
        team_id: int,
        person_id: int,
        name: str | None = None,
        email: str | None = None,
        designation: str | None = None,
        is_lead: bool | None = None,
    ) -> TeamMembership:
        membership = (
            self.db.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id, TeamMembership.person_id == person_id)
            .first()
        )
        if not membership:
            raise ValueError("Member not found on this team")
        team = membership.team
        person = membership.person
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Name is required")
            person.name = name
        if email is not None:
            email_norm = email.strip().lower()
            if not email_norm:
                raise ValueError("Email is required")
            if email_norm != person.email:
                clash = self.get_person_by_email(email_norm)
                if clash and clash.id != person.id:
                    raise ValueError(f"Email '{email}' is already in use")
                person.email = email_norm
        if designation is not None:
            person.role = designation.strip() or None
        if is_lead is not None:
            membership.is_lead = is_lead
        log_activity(
            self.db,
            module="org",
            action="member_updated",
            summary=f"Updated {person.name} on {team.name}",
            entity_type="team",
            entity_id=str(team.id),
            payload={"person_id": person.id, "email": person.email},
        )
        commit_with_retry(self.db)
        return membership

    def remove_team_member(self, team_id: int, person_id: int) -> None:
        membership = (
            self.db.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id, TeamMembership.person_id == person_id)
            .first()
        )
        if not membership:
            raise ValueError("Member not found on this team")
        team_name = membership.team.name
        person_name = membership.person.name
        self.db.delete(membership)
        log_activity(
            self.db,
            module="org",
            action="member_removed",
            summary=f"Removed {person_name} from {team_name}",
            entity_type="team",
            entity_id=str(team_id),
            payload={"person_id": person_id},
        )
        commit_with_retry(self.db)

    def upsert_team(self, name: str, description: str | None = None) -> Team:
        team = self.db.query(Team).filter(Team.name == name.strip()).first()
        if team:
            if description is not None:
                team.description = description
        else:
            team = Team(name=name.strip(), description=description)
            self.db.add(team)
            self.db.flush()
        return team

    def add_team_member(self, team: Team, person: Person, is_lead: bool = False) -> TeamMembership:
        existing = (
            self.db.query(TeamMembership)
            .filter(TeamMembership.team_id == team.id, TeamMembership.person_id == person.id)
            .first()
        )
        if existing:
            existing.is_lead = is_lead
            return existing
        membership = TeamMembership(team_id=team.id, person_id=person.id, is_lead=is_lead)
        self.db.add(membership)
        self.db.flush()
        return membership

    def upsert_customer_account(
        self,
        name: str,
        workshop_name: str,
        support_person: Person | None = None,
        tier: str = "standard",
        industry: str | None = None,
        workshop_email: str | None = None,
        support_contact_email: str | None = None,
        ax_id: str | None = None,
    ) -> CustomerAccount:
        key = normalize_workshop_key(workshop_name)
        account = self.db.query(CustomerAccount).filter(
            CustomerAccount.workshop_name == workshop_name.strip()
        ).first()
        if not account:
            for row in self.db.query(CustomerAccount).all():
                if normalize_workshop_key(row.workshop_name) == key:
                    account = row
                    break
        prev_support_id = account.primary_support_person_id if account else None
        if account:
            account.name = name.strip()
            account.workshop_name = workshop_name.strip()
            account.tier = tier or account.tier
            if industry:
                account.industry = industry
            if support_person:
                account.primary_support_person_id = support_person.id
                if support_contact_email is None and support_person.email:
                    account.support_contact_email = support_person.email.strip().lower()
            if workshop_email is not None:
                account.workshop_email = workshop_email.strip().lower() or None
            if support_contact_email is not None:
                account.support_contact_email = support_contact_email.strip().lower() or None
            if ax_id is not None:
                account.ax_id = normalize_ax_id(ax_id) or None
        else:
            contact = support_contact_email
            if not contact and support_person and support_person.email:
                contact = support_person.email.strip().lower()
            account = CustomerAccount(
                name=name.strip(),
                workshop_name=workshop_name.strip(),
                tier=tier,
                industry=industry,
                workshop_email=workshop_email.strip().lower() if workshop_email else None,
                support_contact_email=contact.strip().lower() if contact else None,
                ax_id=normalize_ax_id(ax_id) or None,
                primary_support_person_id=support_person.id if support_person else None,
            )
            self.db.add(account)
            self.db.flush()
        if support_person and support_person.id != prev_support_id:
            self.db.add(
                CustomerSupportHistory(
                    customer_account_id=account.id,
                    person_id=support_person.id,
                    notes="CSV import or manual update",
                )
            )
        return account

    def create_customer_account_record(
        self,
        workshop_name: str,
        *,
        support_person_name: str | None = None,
        support_person_email: str | None = None,
        workshop_email: str | None = None,
        support_contact_email: str | None = None,
        ax_id: str | None = None,
        tier: str = "standard",
        location: str | None = None,
    ) -> CustomerAccount:
        workshop_name = workshop_name.strip()
        if not workshop_name:
            raise ValueError("Workshop name is required")
        support_person = None
        if support_person_email and support_person_email.strip():
            email = support_person_email.strip().lower()
            display = (support_person_name or email.split("@")[0]).strip()
            support_person = self.upsert_person(display, email, role="support")
        elif support_person_name and support_person_name.strip():
            support_person = self.support_person_from_agent(support_person_name)
        contact = support_contact_email
        if not contact and support_person:
            contact = support_person.email
        account = self.upsert_customer_account(
            name=workshop_name,
            workshop_name=workshop_name,
            support_person=support_person,
            tier=tier or "standard",
            industry=location,
            workshop_email=workshop_email,
            support_contact_email=contact,
            ax_id=ax_id,
        )
        log_activity(
            self.db,
            module="org",
            action="customer_created",
            summary=f"Added workshop: {workshop_name}",
            entity_type="customer_account",
            entity_id=str(account.id),
        )
        commit_with_retry(self.db)
        self.db.refresh(account)
        return account

    def update_customer_account_record(
        self,
        customer_id: int,
        *,
        workshop_name: str | None = None,
        support_person_name: str | None = None,
        support_person_email: str | None = None,
        workshop_email: str | None = None,
        support_contact_email: str | None = None,
        ax_id: str | None = None,
        tier: str | None = None,
        location: str | None = None,
    ) -> CustomerAccount:
        account = self.db.query(CustomerAccount).filter(CustomerAccount.id == customer_id).first()
        if not account:
            raise ValueError("Workshop not found")
        if workshop_name is not None:
            workshop_name = workshop_name.strip()
            if not workshop_name:
                raise ValueError("Workshop name cannot be empty")
            account.name = workshop_name
            account.workshop_name = workshop_name
        if tier is not None:
            account.tier = tier.strip() or account.tier
        if location is not None:
            account.industry = location.strip() or None
        if workshop_email is not None:
            account.workshop_email = workshop_email.strip().lower() or None
        if support_contact_email is not None:
            account.support_contact_email = support_contact_email.strip().lower() or None
        if ax_id is not None:
            account.ax_id = normalize_ax_id(ax_id) or None
        if support_person_email is not None or support_person_name is not None:
            support_person = None
            if support_person_email and support_person_email.strip():
                email = support_person_email.strip().lower()
                display = (support_person_name or email.split("@")[0]).strip()
                support_person = self.upsert_person(display, email, role="support")
            elif support_person_name and support_person_name.strip():
                support_person = self.support_person_from_agent(support_person_name)
            account.primary_support_person_id = support_person.id if support_person else None
            if support_person:
                account.support_contact_email = support_person.email
            if support_person:
                self.db.add(
                    CustomerSupportHistory(
                        customer_account_id=account.id,
                        person_id=support_person.id,
                        notes="Manual update",
                    )
                )
        log_activity(
            self.db,
            module="org",
            action="customer_updated",
            summary=f"Updated workshop: {account.workshop_name}",
            entity_type="customer_account",
            entity_id=str(account.id),
        )
        commit_with_retry(self.db)
        self.db.refresh(account)
        return account

    def delete_customer_account_record(self, customer_id: int) -> None:
        account = self.db.query(CustomerAccount).filter(CustomerAccount.id == customer_id).first()
        if not account:
            raise ValueError("Workshop not found")
        name = account.workshop_name
        self.db.query(CustomerSupportHistory).filter(
            CustomerSupportHistory.customer_account_id == customer_id
        ).delete()
        self.db.delete(account)
        log_activity(
            self.db,
            module="org",
            action="customer_deleted",
            summary=f"Deleted workshop: {name}",
            entity_type="customer_account",
            entity_id=str(customer_id),
        )
        commit_with_retry(self.db)

    def get_support_for_workshop(
        self, workshop_name: str | None, ax_id: str | None = None
    ) -> Person | None:
        account = find_customer_account(self.db, workshop_name, ax_id)
        return account.primary_support if account else None

    def resolve_recipient_emails(
        self,
        team_ids: list[int] | None,
        person_ids: list[int] | None,
        excluded_person_ids: list[int] | None = None,
    ) -> list[str]:
        excluded = set(excluded_person_ids or [])
        emails: set[str] = set()
        if team_ids:
            memberships = (
                self.db.query(TeamMembership)
                .filter(TeamMembership.team_id.in_(team_ids))
                .all()
            )
            person_ids_from_teams = {m.person_id for m in memberships if m.person_id not in excluded}
            people = self.db.query(Person).filter(
                Person.id.in_(person_ids_from_teams), Person.is_active == True  # noqa: E712
            ).all()
            emails.update(p.email for p in people if p.email)
        if person_ids:
            allowed = [pid for pid in person_ids if pid not in excluded]
            people = self.db.query(Person).filter(
                Person.id.in_(allowed), Person.is_active == True  # noqa: E712
            ).all()
            emails.update(p.email for p in people if p.email)
        return sorted(emails)

    def support_person_from_agent(self, agent: str) -> Person | None:
        person = self._person_from_team_roster(agent)
        if person:
            return person
        slug = agent_slug(agent)
        if not slug:
            return None
        email = f"{slug}@support.autorox.co"
        person = self.get_person_by_email(email)
        if person:
            return person
        display = agent_display_name(agent) or slug.replace("-", " ").title()
        return self.upsert_person(display, email, role="support")

    def _person_from_team_roster(self, agent: str) -> Person | None:
        agent = normalize_agent_label(agent)
        slug = agent_slug(agent)
        if not slug:
            return None
        teams = self.list_teams()
        candidates: list[tuple[int, Person]] = []
        for team in teams:
            priority = 0 if "support" in (team.name or "").lower() else 1
            for membership in team.memberships:
                person = membership.person
                if not person or not person.is_active or not person.email:
                    continue
                if agent_names_match(agent, person.name):
                    candidates.append((priority, person))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1].name.lower()))
        return candidates[0][1]

    def reconcile_workshop_support_from_teams(self) -> dict:
        """Point workshops at real team-member emails instead of legacy placeholder addresses."""
        accounts = self.list_customer_accounts()
        updated = 0
        for account in accounts:
            agent_label = account.primary_support.name if account.primary_support else None
            if not agent_label:
                continue
            person = self._person_from_team_roster(agent_label)
            if not person:
                person = self._person_from_team_roster(normalize_agent_label(agent_label))
            if not person:
                continue
            changed = False
            if account.primary_support_person_id != person.id:
                account.primary_support_person_id = person.id
                changed = True
            real_email = person.email.strip().lower()
            if account.support_contact_email != real_email:
                account.support_contact_email = real_email
                changed = True
            if changed:
                updated += 1
        if updated:
            commit_with_retry(self.db)
        return {"updated": updated, "total": len(accounts)}

    def _row_get(self, row: dict, *keys: str) -> str:
        lowered = {k.lower().strip(): v for k, v in row.items()}
        for key in keys:
            val = lowered.get(key.lower())
            if val is not None and str(val).strip():
                return str(val).strip()
        return ""

    def import_teams_csv(self, content: str) -> dict:
        reader = csv.DictReader(io.StringIO(content))
        errors: list[dict] = []
        rows_processed = 0
        for i, row in enumerate(reader, start=2):
            rows_processed += 1
            try:
                team_name = (row.get("team_name") or "").strip()
                member_name = (row.get("member_name") or "").strip()
                member_email = (row.get("member_email") or "").strip()
                is_lead = (row.get("is_lead") or "").strip().lower() in ("1", "true", "yes", "y")
                if not team_name or not member_name or not member_email:
                    errors.append({"row": i, "error": "team_name, member_name, member_email required"})
                    continue
                team = self.upsert_team(team_name)
                person = self.upsert_person(member_name, member_email)
                self.add_team_member(team, person, is_lead=is_lead)
            except Exception as exc:
                errors.append({"row": i, "error": str(exc)})
        log_activity(
            self.db,
            module="org",
            action="csv_imported",
            summary=f"Imported teams CSV ({rows_processed} rows)",
            payload={"type": "teams", "errors": len(errors)},
        )
        commit_with_retry(self.db)
        return {"success": True, "errors": errors, "rows_processed": rows_processed}

    def import_customers_csv(self, content: str) -> dict:
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = [f.lower().strip() for f in (reader.fieldnames or [])]
        if "workshop names" in fieldnames or (
            "agent" in fieldnames and "customer_name" not in fieldnames
        ):
            return self._import_workshops_list_csv(reader)

        errors: list[dict] = []
        count = 0
        for i, row in enumerate(reader, start=2):
            try:
                customer_name = (row.get("customer_name") or "").strip()
                workshop_name = (row.get("workshop_name") or "").strip()
                support_email = (row.get("support_person_email") or "").strip()
                tier = (row.get("tier") or "standard").strip()
                industry = (row.get("industry") or "").strip() or None
                if not customer_name or not workshop_name:
                    errors.append({"row": i, "error": "customer_name and workshop_name required"})
                    continue
                support_person = None
                if support_email:
                    support_person = self.get_person_by_email(support_email)
                    if not support_person:
                        support_person = self.upsert_person(
                            support_email.split("@")[0].replace(".", " ").title(),
                            support_email,
                            role="support",
                        )
                self.upsert_customer_account(
                    customer_name, workshop_name, support_person, tier=tier, industry=industry
                )
                count += 1
            except Exception as exc:
                errors.append({"row": i, "error": str(exc)})
        log_activity(
            self.db,
            module="org",
            action="csv_imported",
            summary=f"Imported customers CSV ({count} accounts)",
            payload={"type": "customers", "count": count, "errors": len(errors)},
        )
        commit_with_retry(self.db)
        return {"success": True, "imported": count, "errors": errors}

    def _import_workshops_list_csv(self, reader: csv.DictReader) -> dict:
        """Import Autorox workshop list: Workshop Names, Agent, Location, AX ID, etc."""
        errors: list[dict] = []
        count = 0
        for i, row in enumerate(reader, start=2):
            try:
                workshop_name = self._row_get(row, "Workshop Names", "workshop_name")
                if not workshop_name:
                    errors.append({"row": i, "error": "Workshop name required"})
                    continue
                agent = self._row_get(row, "Agent", "support_person", "support agent")
                location = self._row_get(row, "Location", "location")
                country = self._row_get(row, "Country", "country")
                ax_id = self._row_get(row, "AX ID", "ax_id", "ax id")
                corporate = self._row_get(row, "Corporate Type", "corporate type", "tier")
                tier = map_corporate_tier(corporate)
                notes_parts = [p for p in (
                    f"Location: {location}" if location else "",
                    f"Country: {country}" if country else "",
                    f"Corporate: {corporate}" if corporate else "",
                ) if p]
                support_person = self.support_person_from_agent(agent)
                contact_email = support_person.email if support_person else None
                account = self.upsert_customer_account(
                    name=workshop_name,
                    workshop_name=workshop_name,
                    support_person=support_person,
                    tier=tier,
                    industry=location or country or None,
                    ax_id=ax_id,
                    support_contact_email=contact_email,
                )
                if notes_parts:
                    account.notes = " | ".join(notes_parts)
                count += 1
            except Exception as exc:
                errors.append({"row": i, "error": str(exc)})
        log_activity(
            self.db,
            module="org",
            action="csv_imported",
            summary=f"Imported workshop list CSV ({count} workshops)",
            payload={"type": "workshops", "count": count, "errors": len(errors)},
        )
        commit_with_retry(self.db)
        return {"success": True, "imported": count, "errors": errors}
