"""OpenAI-powered analysis with intelligent fallback."""

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AIInsight, ExecutiveSummary, AsanaProject
from app.schemas import ChatRequest, ChatResponse
from app.services.analytics import AnalyticsService

settings = get_settings()


class AIService:
    def __init__(
        self,
        db: Session,
        project_gid: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        self.db = db
        self.project_id = None
        if project_gid:
            p = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
            if p:
                self.project_id = p.id
        self.analytics = AnalyticsService(db, project_gid=project_gid, date_from=date_from, date_to=date_to)
        self._client = None
        if settings.openai_api_key:
            self._client = OpenAI(api_key=settings.openai_api_key)

    def get_insights_for_page(self, page: str) -> list[AIInsight]:
        q = self.db.query(AIInsight).filter(AIInsight.page == page)
        if self.project_id:
            q = q.filter(AIInsight.project_id == self.project_id)
        return q.order_by(AIInsight.created_at.desc()).limit(5).all()

    def get_executive_summary(self) -> ExecutiveSummary | None:
        q = self.db.query(ExecutiveSummary)
        if self.project_id:
            q = q.filter(ExecutiveSummary.project_id == self.project_id)
        return q.order_by(ExecutiveSummary.generated_at.desc()).first()

    def chat(self, request: ChatRequest) -> ChatResponse:
        metrics = self.analytics.get_executive_metrics()
        classification = self.analytics.get_classification_analytics()
        blockers = self.analytics.get_blocker_analytics()
        customers = self.analytics.get_customer_pain()
        support = self.analytics.get_support_team_analytics()

        context = (
            f"Current delivery intelligence data:\n"
            f"- Open tickets: {metrics.open_tickets}\n"
            f"- Created today: {metrics.tickets_created_today}\n"
            f"- Closed today: {metrics.tickets_closed_today}\n"
            f"- Avg resolution: {metrics.avg_resolution_hours}h\n"
            f"- Workflow blockers: {blockers.total_blockers}\n"
            f"- SLA compliance: {metrics.sla_compliance_rate}%\n"
            f"- Most common type: {classification.most_common_category}\n"
            f"- Top workshop: {customers.top_pain_customer}\n"
            f"- Top ticket creator: {support.top_creator}\n"
            f"- Top closer: {support.top_closer}\n"
        )

        if self._client:
            try:
                system = (
                    "You are a delivery intelligence assistant. RULES:\n"
                    "1. Use ONLY numbers from the Context below.\n"
                    "2. If data is insufficient, say 'Not available in current analytics.'\n"
                    "3. Never invent ticket titles, assignees, or root causes.\n"
                    "4. Be concise and actionable.\n"
                    f"Context:\n{context}"
                )
                messages = [{"role": "system", "content": system}]
                history = request.conversation_history[-10:]
                for msg in history:
                    messages.append({"role": msg.role, "content": msg.content})
                # Avoid duplicating the current user turn if already in history
                if not history or history[-1].content != request.message or history[-1].role != "user":
                    messages.append({"role": "user", "content": request.message})

                response = self._client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.3,
                )
                answer = response.choices[0].message.content or ""
                return ChatResponse(
                    response=answer,
                    sources=[{"type": "analytics", "label": "Live ticket data"}],
                    suggested_followups=[
                        "Which module has the most critical tickets?",
                        "Show me SLA compliance trends",
                        "Who are the top 3 customers by ticket volume?",
                    ],
                )
            except Exception:
                pass

        return self._mock_chat_response(request.message, context)

    def _mock_chat_response(self, message: str, context: str) -> ChatResponse:
        msg = message.lower()
        if "critical" in msg or "blocker" in msg:
            blockers = self.analytics.get_blocker_analytics()
            response = f"There are currently {blockers.total_blockers} critical workflow blockers affecting {blockers.affected_customers} customers. Average time blocked: {blockers.avg_days_blocked} days."
        elif "module" in msg or "heatmap" in msg:
            heatmap = self.analytics.get_heatmap_analytics()
            top3 = heatmap.modules[:3]
            response = f"The hottest modules are: {', '.join(f'{m.module} ({m.ticket_count} tickets)' for m in top3)}. {heatmap.hottest_module} has the highest ticket volume."
        elif "sla" in msg or "resolution" in msg:
            res = self.analytics.get_resolution_analytics()
            response = f"Average resolution time is {res.avg_resolution_hours}h (median: {res.median_resolution_hours}h). SLA compliance rate is {res.sla_compliance_rate}%. {res.reopened_count} tickets have been reopened ({res.reopened_rate}%)."
        elif "customer" in msg or "pain" in msg or "workshop" in msg:
            pain = self.analytics.get_customer_pain()
            top3 = pain.customers[:3]
            response = f"Top workshops by ticket volume: {', '.join(f'{c.customer_name} ({c.ticket_count} tickets)' for c in top3)}."
        elif "support" in msg or "team" in msg or "creator" in msg:
            team = self.analytics.get_support_team_analytics()
            response = f"Top creator: {team.top_creator}. Top closer: {team.top_closer}. {team.total_members} team members tracked."
        elif "classif" in msg or "type" in msg:
            cls = self.analytics.get_classification_analytics()
            response = f"Ticket types from Asana: {', '.join(f'{c.category} ({c.count})' for c in cls.support_breakdown[:4])}."
        else:
            metrics = self.analytics.get_executive_metrics()
            response = (
                f"Based on current data: {metrics.open_tickets} open tickets, "
                f"{metrics.tickets_created_today} created today, "
                f"{metrics.tickets_closed_today} closed today. "
                f"Average resolution time is {metrics.avg_resolution_hours} hours with "
                f"{metrics.sla_compliance_rate}% SLA compliance."
            )

        return ChatResponse(
            response=response,
            sources=[{"type": "mock_analytics", "label": "Ticket database"}],
            suggested_followups=[
                "Which workshops have the most open tickets?",
                "Who created the most tickets this period?",
                "What are the current workflow blockers?",
            ],
        )

    def classify_ticket(self, title: str, description: str) -> str:
        """AI ticket classification logic."""
        text = f"{title} {description}".lower()
        if any(w in text for w in ["crash", "error", "fail", "broken", "bug", "exception"]):
            return "bug"
        if any(w in text for w in ["feature", "enhance", "improve", "add", "request"]):
            return "enhancement"
        if any(w in text for w in ["config", "setting", "setup", "configure"]):
            return "configuration"
        if any(w in text for w in ["how to", "documentation", "guide", "help", "knowledge"]):
            return "knowledge_gap"
        if any(w in text for w in ["duplicate", "already reported", "same issue"]):
            return "duplicate"
        return "bug"
