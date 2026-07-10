"""Topic-first clustering, then symptom-similarity sub-groups within each module."""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Ticket, IssueCluster, TicketStatus, Module, ClusterAnalysisJob, ClusterAnalysisResult
from app.services.ticket_parser import infer_primary_module
from app.services.symptom_grouping import (
    LABEL_STOP,
    problem_signature,
    theme_label,
    cluster_labels,
)

# Re-export for cluster_analysis back-compat
DOMAIN_STOP = LABEL_STOP


def _get_or_create_topic_module(db: Session, topic: str, project_id: int) -> Module:
    mod = db.query(Module).filter(Module.name == topic, Module.project_id == project_id).first()
    if not mod:
        mod = Module(name=topic, product_area="Ticket Topic", project_id=project_id)
        db.add(mod)
        db.flush()
    return mod


def _semantic_subclusters(
    tickets: list[Ticket],
    ticket_indices: list[int],
    min_cluster_size: int,
) -> dict[int, list[int]]:
    """Group by same symptom wording within a module bucket."""
    if len(ticket_indices) < min_cluster_size:
        return {}

    signatures = [
        problem_signature(tickets[i].title or "", tickets[i].description or "")
        for i in ticket_indices
    ]
    labels = cluster_labels(signatures)

    groups: dict[int, list[int]] = defaultdict(list)
    for local_idx, label in enumerate(labels):
        groups[int(label)].append(ticket_indices[local_idx])

    return {k: v for k, v in groups.items() if len(v) >= min_cluster_size}


def _clear_project_clusters(db: Session, project_id: int) -> None:
    old_clusters = db.query(IssueCluster).filter(IssueCluster.project_id == project_id).all()
    for c in old_clusters:
        jobs = db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.cluster_id == c.id).all()
        for job in jobs:
            db.query(ClusterAnalysisResult).filter(ClusterAnalysisResult.job_id == job.id).delete()
            db.delete(job)
        db.query(Ticket).filter(Ticket.cluster_id == c.id).update({Ticket.cluster_id: None})
        db.delete(c)
    db.flush()


def run_semantic_clustering(db: Session, project_id: int, min_cluster_size: int = 2) -> int:
    """
    Cluster tickets in two stages:
    1) Split by module topic (Invoice vs Job Card vs …).
    2) Within each module, group tickets with the same symptom in different wording.
    """
    tickets = db.query(Ticket).filter(
        Ticket.project_id == project_id,
        Ticket.title.isnot(None),
    ).all()

    if len(tickets) < min_cluster_size:
        return 0

    topic_groups: dict[str, list[int]] = defaultdict(list)
    for i, ticket in enumerate(tickets):
        topic = infer_primary_module(ticket.title or "", ticket.description or "")
        topic_groups[topic].append(i)

    _clear_project_clusters(db, project_id)

    created = 0
    for topic, ticket_indices in topic_groups.items():
        if len(ticket_indices) < min_cluster_size:
            continue

        sub_groups = _semantic_subclusters(tickets, ticket_indices, min_cluster_size)
        topic_module = _get_or_create_topic_module(db, topic, project_id)

        for sub_indices in sub_groups.values():
            group_tickets = [tickets[i] for i in sub_indices]
            titles = [t.title or "" for t in group_tickets]
            theme = theme_label(titles, topic)
            name = f"{topic} · {theme}" if theme and theme != "Related issues" else topic

            open_count = sum(1 for t in group_tickets if t.status != TicketStatus.CLOSED)
            severity = (
                "critical" if open_count >= 5
                else "high" if open_count >= 2
                else "medium"
            )

            cluster = IssueCluster(
                name=name,
                description=f"{len(group_tickets)} tickets — same symptom reported in different wording",
                ai_summary=(
                    f"{topic} — {theme}. "
                    f"{len(group_tickets)} tickets. Sample: {titles[0][:100]}"
                ),
                ticket_count=len(group_tickets),
                severity=severity,
                project_id=project_id,
                module_id=topic_module.id,
            )
            db.add(cluster)
            db.flush()
            for t in group_tickets:
                t.cluster_id = cluster.id
            created += 1

    db.commit()
    return created
