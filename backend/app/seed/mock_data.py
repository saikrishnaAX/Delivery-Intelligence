"""Comprehensive mock data generator for development and demos."""

import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import (
    Customer, Module, Ticket, IssueCluster, JiraIssue, AsanaProject,
    AIInsight, ExecutiveSummary,
    TicketStatus, TicketCategory, TicketPriority,
)

MODULES = [
    ("Authentication", "Platform", "User login, SSO, MFA"),
    ("Billing", "Commerce", "Invoicing, payments, subscriptions"),
    ("Reporting", "Analytics", "Dashboards, exports, scheduled reports"),
    ("API Gateway", "Platform", "REST/GraphQL APIs, rate limiting"),
    ("Notifications", "Communication", "Email, SMS, push notifications"),
    ("Inventory", "Operations", "Stock management, warehouses"),
    ("User Management", "Platform", "Roles, permissions, org structure"),
    ("Integrations", "Platform", "Third-party connectors, webhooks"),
    ("Mobile App", "Client", "iOS and Android applications"),
    ("Search", "Platform", "Full-text search, filters, indexing"),
]

CUSTOMERS = [
    ("Acme Corp", "enterprise", "Manufacturing"),
    ("Globex Industries", "enterprise", "Technology"),
    ("Initech", "standard", "Finance"),
    ("Umbrella Systems", "premium", "Healthcare"),
    ("Stark Logistics", "enterprise", "Logistics"),
    ("Wayne Analytics", "premium", "Data Services"),
    ("Oscorp Digital", "standard", "Retail"),
    ("LexCorp", "enterprise", "Energy"),
    ("Daily Planet Media", "standard", "Media"),
    ("Cyberdyne Tech", "premium", "AI/ML"),
]

TICKET_TITLES = [
    "Login fails with SSO on mobile",
    "Invoice PDF generation timeout",
    "Dashboard export missing columns",
    "API rate limit exceeded unexpectedly",
    "Email notifications delayed by 2+ hours",
    "Inventory sync fails for warehouse B",
    "Role assignment not reflecting immediately",
    "Webhook delivery retries exhausted",
    "App crashes on iOS 17.4",
    "Search returns stale results after update",
    "Payment gateway timeout on checkout",
    "Report scheduler runs twice daily",
    "MFA enrollment loop on first login",
    "API pagination returns duplicate records",
    "Push notifications not received on Android",
    "Stock count mismatch after bulk import",
    "Permission denied for admin users",
    "Slack integration OAuth token expired",
    "Offline mode data not syncing",
    "Search filter ignores date range",
    "Subscription renewal email not sent",
    "Chart rendering broken in Safari",
    "Bulk user import validation errors",
    "Rate limit config not persisting",
    "SMS OTP delivery failure in EU region",
]

CLUSTER_NAMES = [
    "SSO Authentication Failures",
    "Payment Processing Timeouts",
    "Mobile App Stability Issues",
    "API Rate Limiting Problems",
    "Notification Delivery Delays",
    "Search Index Staleness",
    "Permission Sync Lag",
    "Webhook Reliability Issues",
]

ASSIGNEES = ["Alex Chen", "Jordan Lee", "Sam Patel", "Taylor Kim", "Morgan Davis", "Casey Wong"]
REPORTERS = ["Support Team", "Customer Success", "Engineering", "QA Team", "Product"]


def seed_database(db: Session) -> None:
    if db.query(Ticket).count() > 0:
        return

    demo_project = AsanaProject(
        gid="mock_project_001",
        name="Demo Delivery Project",
        workspace_gid="mock_workspace",
        jira_project_key="DEL",
        ticket_count=0,
    )
    db.add(demo_project)
    db.flush()

    modules = []
    for name, area, desc in MODULES:
        m = Module(name=name, product_area=area, description=desc, project_id=demo_project.id)
        db.add(m)
        modules.append(m)
    db.flush()

    customers = []
    for name, tier, industry in CUSTOMERS:
        c = Customer(name=name, tier=tier, industry=industry)
        db.add(c)
        customers.append(c)
    db.flush()

    clusters = []
    for i, cname in enumerate(CLUSTER_NAMES):
        cluster = IssueCluster(
            name=cname,
            description=f"AI-detected cluster of related issues in {modules[i % len(modules)].name}",
            ai_summary=f"Multiple tickets report similar symptoms related to {cname.lower()}. "
                       f"Root cause analysis suggests a common underlying issue.",
            ticket_count=0,
            severity=random.choice(["high", "medium", "critical"]),
            module_id=modules[i % len(modules)].id,
            project_id=demo_project.id,
        )
        db.add(cluster)
        clusters.append(cluster)
    db.flush()

    now = datetime.utcnow()
    tickets = []
    statuses = list(TicketStatus)
    categories = list(TicketCategory)
    priorities = list(TicketPriority)

    for i in range(200):
        days_ago = random.randint(0, 90)
        created = now - timedelta(days=days_ago, hours=random.randint(0, 23))
        status = random.choices(
            statuses,
            weights=[30, 25, 40, 5],
        )[0]
        support_cat = random.choice(categories)
        ai_cat = support_cat if random.random() > 0.25 else random.choice(categories)
        priority = random.choices(priorities, weights=[20, 40, 30, 10])[0]
        is_blocker = priority == TicketPriority.CRITICAL and status != TicketStatus.CLOSED
        is_reopened = status == TicketStatus.CLOSED and random.random() < 0.08

        closed_at = None
        resolution_hours = None
        sla_met = None
        if status == TicketStatus.CLOSED:
            resolution_hours = random.uniform(2, 120)
            closed_at = created + timedelta(hours=resolution_hours)
            sla_met = resolution_hours <= 48

        if days_ago == 0 and random.random() < 0.3:
            created = now - timedelta(hours=random.randint(1, 12))

        cluster = random.choice(clusters) if random.random() < 0.6 else None
        module = random.choice(modules)
        customer = random.choice(customers)
        title = random.choice(TICKET_TITLES)
        jira_key = f"DEL-{1000 + i}" if random.random() < 0.5 else None

        ticket = Ticket(
            asana_gid=f"asana_{10000 + i}",
            title=f"{title} #{i + 1}",
            description=f"Customer reported: {title}. Affected module: {module.name}. "
                        f"Customer: {customer.name}. Priority: {priority.value}.",
            status=status,
            support_category=support_cat,
            ai_category=ai_cat,
            priority=priority,
            module_id=module.id,
            customer_id=customer.id,
            project_id=demo_project.id,
            assignee=random.choice(ASSIGNEES),
            reporter=random.choice(REPORTERS),
            is_critical_blocker=is_blocker,
            is_reopened=is_reopened,
            sla_hours=48,
            sla_met=sla_met,
            resolution_hours=resolution_hours,
            cluster_id=cluster.id if cluster else None,
            jira_key=jira_key,
            tags=random.sample(["urgent", "regression", "customer-reported", "production", "needs-triage"], k=random.randint(0, 3)),
            asana_url=f"https://app.asana.com/0/0/{10000 + i}",
            created_at=created,
            closed_at=closed_at,
        )
        db.add(ticket)
        tickets.append(ticket)

    db.flush()

    for cluster in clusters:
        cluster.ticket_count = db.query(Ticket).filter(Ticket.cluster_id == cluster.id).count()

    sprints = ["Sprint 24", "Sprint 25", "Sprint 26"]
    for ticket in tickets:
        if ticket.jira_key:
            ji = JiraIssue(
                ticket_id=ticket.id,
                project_id=demo_project.id,
                project_key="DEL",
                jira_key=ticket.jira_key,
                summary=ticket.title,
                status=random.choice(["To Do", "In Progress", "In Review", "Done"]),
                issue_type=random.choice(["Bug", "Story", "Task"]),
                sprint_name=random.choice(sprints),
                sprint_state=random.choice(["active", "closed", "future"]),
                story_points=random.choice([1, 2, 3, 5, 8, None]),
                assignee=ticket.assignee,
                jira_url=f"https://jira.example.com/browse/{ticket.jira_key}",
            )
            db.add(ji)

    insights_data = [
        ("executive", "trend", "Ticket Volume Increasing", "Created tickets are up 12% week-over-week. Billing and Authentication modules show the highest growth.", "warning"),
        ("executive", "sla", "SLA Compliance Stable", "Overall SLA compliance remains at 87%, within the 85% target threshold.", "info"),
        ("classification", "insight", "Knowledge Gap Trending", "Knowledge Gap tickets increased 18% this month, suggesting documentation gaps in Integrations.", "warning"),
        ("clustering", "insight", "SSO Cluster Critical", "The SSO Authentication Failures cluster has 15 open tickets — recommend immediate engineering review.", "critical"),
        ("heatmap", "insight", "Billing Module Hotspot", "Billing accounts for 22% of all tickets with the longest average resolution time.", "warning"),
        ("accuracy", "insight", "Classification Drift", "Support team misclassifies 23% of Configuration issues as Bugs.", "warning"),
        ("blockers", "insight", "3 Critical Blockers Active", "Three critical workflow blockers are affecting enterprise customers.", "critical"),
        ("customers", "insight", "Acme Corp Escalation Risk", "Acme Corp has submitted 28 tickets this month with 4 critical issues — highest pain score.", "critical"),
        ("jira", "insight", "Sprint 26 Capacity", "Sprint 26 has 34 story points committed with 12 linked support tickets.", "info"),
        ("resolution", "insight", "Resolution Time Improving", "Average resolution time decreased from 36h to 28h over the past 30 days.", "info"),
        ("assistant", "insight", "Ask About Trends", "Try asking: 'Which module has the most open critical tickets?'", "info"),
    ]

    for page, itype, title, content, severity in insights_data:
        db.add(AIInsight(page=page, insight_type=itype, title=title, content=content, severity=severity, project_id=demo_project.id))

    db.add(ExecutiveSummary(
        project_id=demo_project.id,
        summary="Delivery intelligence shows stable operations with 12% increase in ticket volume. "
                "Authentication and Billing modules require attention. SLA compliance at 87% meets targets. "
                "Three critical blockers need immediate resolution. Acme Corp shows highest customer pain score.",
        key_metrics={
            "open_tickets": 72,
            "sla_compliance": 87.0,
            "critical_blockers": 3,
            "avg_resolution_hours": 28.4,
        },
        recommendations=[
            "Prioritize SSO authentication cluster resolution",
            "Schedule knowledge base update for Integrations module",
            "Engage Acme Corp account team for escalation review",
            "Review support classification training for Configuration tickets",
        ],
    ))

    demo_project.ticket_count = db.query(Ticket).filter(Ticket.project_id == demo_project.id).count()
    db.commit()
