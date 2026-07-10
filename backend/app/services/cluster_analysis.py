"""Product defect discovery — keyword grouping first, optional OpenAI refine."""

import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime

from openai import OpenAI
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    IssueCluster,
    Ticket,
    TicketStatus,
    ClusterAnalysisJob,
    ClusterAnalysisResult,
)
from app.services.activity_log import log_activity
from app.services.ticket_parser import infer_module_affected

logger = logging.getLogger(__name__)
settings = get_settings()

from app.services.symptom_grouping import (
    DOMAIN_STOP,
    KEYWORD_STOP,
    SYMPTOM_CLUSTER_DISTANCE,
    CORPUS_STOP_DOC_FREQ,
    problem_signature,
    corpus_specific_stops,
    representative_title,
    cluster_labels,
    significant_words,
)

MIN_TICKETS_FOR_DEFECT = 1
STALE_JOB_SECONDS = 15 * 60
PROGRESS_CHUNK = 25

ANALYST_SYSTEM = (
    "You are an Expert Product Analyst, QA Lead, and Root Cause Investigator for Autorox, "
    "a garage/workshop management platform. Your task is NOT to summarize tickets. "
    "Your task is to discover actual product defects. Many tickets describe the same bug "
    "using different wording. Merge duplicates into unique product issues. "
    "Think like a Product Manager. Return only issues backed by evidence from tickets. "
    "Return valid JSON only."
)


class ClusterAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self._fast_mode = True
        use_ai = settings.cluster_analysis_use_openai and bool(settings.openai_api_key)
        self._client = OpenAI(api_key=settings.openai_api_key) if use_ai else None

    def _disable_llm(self, reason: str) -> None:
        if not self._fast_mode:
            logger.warning("%s — switching to fast keyword analysis for this job", reason)
        self._fast_mode = True
        self._client = None

    def get_cluster_tickets(self, cluster_id: int, status: str = "all") -> list[Ticket]:
        q = (
            self.db.query(Ticket)
            .options(joinedload(Ticket.module))
            .filter(Ticket.cluster_id == cluster_id)
        )
        if status == "open":
            q = q.filter(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED])
            )
        return q.order_by(Ticket.created_at.desc()).all()

    def get_open_tickets(self, cluster_id: int) -> list[Ticket]:
        return self.get_cluster_tickets(cluster_id, status="open")

    def count_open_tickets(self, cluster_id: int) -> int:
        return (
            self.db.query(Ticket)
            .filter(
                Ticket.cluster_id == cluster_id,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED]),
            )
            .count()
        )

    def get_active_job(self, cluster_id: int) -> ClusterAnalysisJob | None:
        self.recover_stale_jobs(cluster_id)
        return (
            self.db.query(ClusterAnalysisJob)
            .filter(
                ClusterAnalysisJob.cluster_id == cluster_id,
                ClusterAnalysisJob.status.in_(["pending", "running"]),
            )
            .order_by(ClusterAnalysisJob.created_at.desc())
            .first()
        )

    def recover_stale_jobs(self, cluster_id: int | None = None) -> int:
        """Mark abandoned pending/running jobs as failed so analysis can be restarted."""
        q = self.db.query(ClusterAnalysisJob).filter(
            ClusterAnalysisJob.status.in_(["pending", "running"]),
        )
        if cluster_id is not None:
            q = q.filter(ClusterAnalysisJob.cluster_id == cluster_id)
        now = datetime.utcnow()
        recovered = 0
        for job in q.all():
            anchor = job.started_at or job.created_at
            if not anchor:
                continue
            age = (now - anchor).total_seconds()
            stuck = (
                age > STALE_JOB_SECONDS
                or (job.status == "running" and job.tickets_processed == 0 and age > 45)
                or (
                    job.status == "running"
                    and job.tickets_total > 0
                    and job.tickets_processed >= job.tickets_total
                    and age > 180
                )
            )
            if stuck:
                job.status = "failed"
                job.error_message = "Analysis was interrupted or timed out. Please run again."
                job.completed_at = now
                recovered += 1
        if recovered:
            self.db.commit()
        return recovered

    def get_latest_completed_job(
        self, cluster_id: int, *, include_dismissed: bool = False
    ) -> ClusterAnalysisJob | None:
        q = (
            self.db.query(ClusterAnalysisJob)
            .filter(
                ClusterAnalysisJob.cluster_id == cluster_id,
                ClusterAnalysisJob.status == "completed",
            )
        )
        if not include_dismissed:
            q = q.filter(ClusterAnalysisJob.dismissed_at.is_(None))
        return q.order_by(ClusterAnalysisJob.completed_at.desc()).first()

    def can_start_analysis(self, cluster_id: int) -> tuple[bool, str]:
        self.recover_stale_jobs(cluster_id)
        if self.get_active_job(cluster_id):
            return False, "An analysis is already running for this cluster."
        latest = self.get_latest_completed_job(cluster_id)
        if not latest:
            return True, ""
        open_now = self.count_open_tickets(cluster_id)
        snapshot = latest.open_ticket_count_snapshot or 0
        if open_now > snapshot:
            return True, ""
        return (
            False,
            "Dismiss the intelligence report or wait until new open tickets are added to this cluster.",
        )

    def dismiss_latest_analysis(self, cluster_id: int) -> ClusterAnalysisJob | None:
        job = self.get_latest_completed_job(cluster_id)
        if not job:
            return None
        job.dismissed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job

    def _update_progress(self, job_id: int, processed: int) -> None:
        job = self.db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.id == job_id).first()
        if job:
            job.tickets_processed = processed
            self.db.commit()

    def _run_job(self, job: ClusterAnalysisJob, tickets: list[Ticket], batch_size: int) -> None:
        job_id = job.id
        try:
            job = self.db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.id == job_id).first()
            if not job:
                return
            job.status = "running"
            job.started_at = datetime.utcnow()
            self.db.commit()

            cluster_total = len(tickets)
            ticket_by_id = {t.id: t for t in tickets}

            # Phase 1 — read tickets (fast local scan, updates progress bar)
            for i in range(0, len(tickets), PROGRESS_CHUNK):
                self._update_progress(job_id, min(i + PROGRESS_CHUNK, cluster_total))
                time.sleep(0.02)

            # Phase 2 — keyword / TF-IDF grouping (seconds, no per-ticket API calls)
            defects = self._keyword_group_tickets(tickets)
            if self._client:
                defects = self._optional_llm_refine(defects, tickets, cluster_total)

            self._update_progress(job_id, cluster_total)

            reports: list[dict] = []
            for defect in defects:
                ids = defect.get("ticket_ids", [])
                if len(ids) < MIN_TICKETS_FOR_DEFECT:
                    continue
                share = len(ids) / cluster_total if cluster_total else 0
                group = [ticket_by_id[tid] for tid in ids if tid in ticket_by_id]
                if not group:
                    continue
                intel = self._build_intelligence_report(defect, group, cluster_total, share, fast=True)
                reports.append(intel)

            job = self.db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.id == job_id).first()
            if not job:
                return

            for report in reports:
                self.db.add(
                    ClusterAnalysisResult(
                        job_id=job.id,
                        theme_title=report["issue_name"],
                        one_line_issue=report.get("root_cause", ""),
                        ticket_ids=report.get("ticket_ids", []),
                        suggested_test_cases=report.get("regression_test_cases", []),
                        confidence=report.get("confidence"),
                        topic_module=report.get("affected_module"),
                        ticket_percentage=report.get("ticket_percentage"),
                        intelligence=report,
                    )
                )

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.tickets_processed = job.tickets_total
            cluster = self.db.query(IssueCluster).filter(IssueCluster.id == job.cluster_id).first()
            log_activity(
                self.db,
                module="clustering",
                action="analysis_completed",
                summary=(
                    f"Defect intelligence: {cluster.name if cluster else job.cluster_id} "
                    f"— {len(reports)} product defects from {cluster_total} tickets"
                ),
                entity_type="cluster",
                entity_id=str(job.cluster_id),
                payload={"job_id": job.id, "defects": len(reports), "tickets": cluster_total},
            )
            self.db.commit()
        except Exception as exc:
            logger.exception("Cluster analysis job %s failed", job_id)
            job = self.db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:500]
                job.completed_at = datetime.utcnow()
                self.db.commit()

    @staticmethod
    def _normalize_ticket_text(ticket: Ticket) -> str:
        text = f"{ticket.title or ''} {(ticket.description or '')[:500]}".lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _problem_signature(cls, ticket: Ticket) -> str:
        """Strip module/boilerplate words — keep the symptom phrasing that differs between issues."""
        raw = cls._normalize_ticket_text(ticket)
        words = []
        for w in raw.split():
            if len(w) <= 2:
                continue
            if w in DOMAIN_STOP or w in KEYWORD_STOP:
                continue
            words.append(w)
        return " ".join(words) if words else raw

    @staticmethod
    def _corpus_specific_stops(signatures: list[str], max_doc_freq: float = CORPUS_STOP_DOC_FREQ) -> set[str]:
        n = len(signatures)
        if n < 3:
            return set()
        doc_freq: Counter[str] = Counter()
        for sig in signatures:
            for w in set(sig.split()):
                doc_freq[w] += 1
        return {w for w, c in doc_freq.items() if c / n >= max_doc_freq}

    @classmethod
    def _significant_words(cls, text: str, extra_stop: set[str] | None = None) -> list[str]:
        stop = DOMAIN_STOP | KEYWORD_STOP | (extra_stop or set())
        words = []
        for w in text.split():
            if len(w) > 2 and w not in stop:
                words.append(w)
        return words

    @classmethod
    def _representative_title(cls, titles: list[str], local_stops: set[str]) -> str:
        """Pick the ticket title that best represents shared symptom wording."""
        if not titles:
            return "Reported issue"
        if len(titles) == 1:
            return titles[0][:100]

        def word_set(title: str) -> set[str]:
            return set(cls._significant_words(title.lower(), local_stops))

        best_title = titles[0]
        best_score = -1.0
        for t in titles:
            ws = word_set(t)
            if not ws:
                continue
            others = [word_set(o) for o in titles if o != t]
            if not others:
                continue
            score = sum(len(ws & o) / max(len(ws | o), 1) for o in others) / len(others)
            if score > best_score:
                best_score = score
                best_title = t
        return best_title[:100]

    @classmethod
    def _distinctive_keywords(
        cls, tickets: list[Ticket], local_stops: set[str], limit: int = 6
    ) -> list[str]:
        words: list[str] = []
        for t in tickets:
            sig = cls._problem_signature(t)
            words.extend(cls._significant_words(sig, local_stops))
        return [w for w, _ in Counter(words).most_common(limit)]

    @classmethod
    def _theme_label_from_titles(cls, titles: list[str], local_stops: set[str] | None = None) -> str:
        return cls._representative_title(titles, local_stops or set())

    @classmethod
    def _top_keywords_for_group(cls, tickets: list[Ticket], limit: int = 6) -> list[str]:
        local = cls._corpus_specific_stops([cls._problem_signature(t) for t in tickets])
        return cls._distinctive_keywords(tickets, local, limit)

    def _keyword_group_tickets(self, tickets: list[Ticket]) -> list[dict]:
        """Group tickets describing the same symptom in different words — not shared module names."""
        if not tickets:
            return []

        n = len(tickets)
        signatures = [self._problem_signature(t) for t in tickets]
        local_stops = self._corpus_specific_stops(signatures)
        combined_stop = DOMAIN_STOP | KEYWORD_STOP | local_stops

        if n == 1:
            t = tickets[0]
            title = (t.title or "Reported issue").strip()
            return [{
                "issue_name": title[:100],
                "root_cause": "Distinct symptom — no duplicate wording found in this cluster.",
                "ticket_ids": [t.id],
                "evidence_summary": title[:200],
                "confidence": 0.4,
                "top_keywords": self._distinctive_keywords([t], local_stops),
            }]

        try:
            from sklearn.cluster import AgglomerativeClustering
            from sklearn.feature_extraction.text import TfidfVectorizer

            # Rebuild signatures excluding corpus-common words (e.g. "status" in every job-card ticket).
            refined = []
            for sig in signatures:
                words = [w for w in sig.split() if w not in local_stops]
                refined.append(" ".join(words) if words else sig)

            stop_list = list(combined_stop)
            vectorizer = TfidfVectorizer(
                max_features=500,
                stop_words=stop_list,
                min_df=1,
                max_df=0.85,
                ngram_range=(1, 2),
                sublinear_tf=True,
            )
            matrix = vectorizer.fit_transform(refined)
            dense = matrix.toarray()

            if dense.shape[1] == 0:
                raise ValueError("empty vocabulary")

            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=SYMPTOM_CLUSTER_DISTANCE,
                metric="cosine",
                linkage="average",
            )
            labels = clustering.fit_predict(dense)

            groups: dict[int, list[Ticket]] = defaultdict(list)
            for idx, ticket in enumerate(tickets):
                groups[int(labels[idx])].append(ticket)

            defects: list[dict] = []
            for group in groups.values():
                titles = [(t.title or "").strip() for t in group if t.title]
                keywords = self._distinctive_keywords(group, local_stops)
                issue_name = self._representative_title(titles, local_stops)
                sample = "; ".join(titles[:3])
                same_symptom = len(group) > 1
                defects.append({
                    "issue_name": issue_name,
                    "root_cause": (
                        f"Same symptom in different wording"
                        + (f" — shared terms: {', '.join(keywords[:5])}" if keywords else "")
                        if same_symptom
                        else "Unique symptom — not merged with other tickets."
                    ),
                    "ticket_ids": [t.id for t in group],
                    "evidence_summary": f"{len(group)} ticket(s) — {sample[:220]}",
                    "confidence": round(0.4 + min(0.5, len(group) / max(n, 1)), 2) if same_symptom else 0.35,
                    "top_keywords": keywords,
                })

            return sorted(defects, key=lambda d: len(d["ticket_ids"]), reverse=True)
        except Exception:
            logger.exception("Symptom similarity grouping failed — listing per ticket")
            return [
                {
                    "issue_name": (t.title or "Reported issue")[:100],
                    "root_cause": "Unique symptom — not merged with other tickets.",
                    "ticket_ids": [t.id],
                    "evidence_summary": (t.title or "")[:200],
                    "confidence": 0.35,
                    "top_keywords": self._distinctive_keywords([t], local_stops),
                }
                for t in tickets
            ]

    def _optional_llm_refine(
        self, defects: list[dict], tickets: list[Ticket], cluster_total: int
    ) -> list[dict]:
        """One optional OpenAI call to polish group names (only when explicitly enabled)."""
        if not self._client or not defects:
            return defects

        ticket_by_id = {t.id: t for t in tickets}
        compact = []
        for d in defects[:35]:
            ids = d.get("ticket_ids", [])[:8]
            titles = [
                (ticket_by_id[tid].title or "")[:80]
                for tid in ids
                if tid in ticket_by_id
            ]
            compact.append({
                "ticket_ids": d.get("ticket_ids", []),
                "current_name": d.get("issue_name"),
                "sample_titles": titles,
                "keywords": d.get("top_keywords", []),
            })

        prompt = (
            f"These are {len(defects)} keyword-grouped issue clusters from {cluster_total} support tickets.\n"
            "For each group, return a clearer product defect title (issue_name) a PM would use.\n"
            "Keep the same ticket_ids. Do not merge groups.\n"
            "Return JSON array: "
            '[{"ticket_ids": [...], "issue_name": "...", "evidence_summary": "one line"}]\n\n'
            f"Groups:\n{json.dumps(compact)}"
        )
        try:
            parsed = self._llm_json(prompt, temperature=0.2)
            if not isinstance(parsed, list):
                return defects
            refined_by_ids: dict[frozenset, dict] = {}
            for item in parsed:
                ids = item.get("ticket_ids") or []
                if ids:
                    refined_by_ids[frozenset(ids)] = item
            out = []
            for d in defects:
                key = frozenset(d.get("ticket_ids", []))
                if key in refined_by_ids:
                    r = refined_by_ids[key]
                    d = {**d, "issue_name": r.get("issue_name", d["issue_name"])}
                    if r.get("evidence_summary"):
                        d["evidence_summary"] = r["evidence_summary"]
                out.append(d)
            return out
        except Exception:
            logger.exception("Optional LLM refine skipped")
            self._disable_llm("OpenAI refine failed")
            return defects

    def _extract_defects_batch(self, tickets: list[Ticket]) -> list[dict]:
        if self._fast_mode or not self._client:
            return [self._fallback_extraction(t) for t in tickets]

        items = []
        for t in tickets:
            items.append({
                "ticket_id": t.id,
                "title": t.title,
                "description": (t.description or "")[:900],
                "status": t.status.value if t.status else "open",
                "workshop": t.workshop_name,
                "build": t.build_in,
                "product_stage": t.product_stage,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            })

        prompt = (
            "Analyze each ticket below. Extract the ACTUAL product defect being reported — "
            "not a summary of the title.\n\n"
            "For each ticket return:\n"
            '- defect_hypothesis: the specific product bug or failure mode (one sentence)\n'
            '- complaint: verbatim user pain in short quote form if visible\n'
            '- resolution_mentioned: what fix/resolution is stated in the ticket text, or null if none\n'
            '- module_hint: affected product area inferred from content\n\n'
            "Do NOT write generic statements. Use evidence from the description.\n"
            "Return JSON array: "
            '[{"ticket_id": <id>, "defect_hypothesis": "...", "complaint": "...", '
            '"resolution_mentioned": "..." | null, "module_hint": "..."}]\n\n'
            f"Tickets:\n{json.dumps(items)}"
        )
        try:
            parsed = self._llm_json(prompt, temperature=0.15)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            logger.exception("Defect extraction batch failed")
            self._disable_llm("OpenAI extraction failed")
            return [self._fallback_extraction(t) for t in tickets]

    def _finalize_defects(self, extractions: list[dict], cluster_total: int) -> list[dict]:
        """Merge extractions into defects; never return empty when tickets were analyzed."""
        if not extractions:
            return []

        defects = self._merge_defects(extractions, cluster_total)
        if not defects:
            logger.warning("LLM merge returned no defects — using keyword merge fallback")
            defects = self._fallback_merge(extractions, min_tickets=1)

        if not defects:
            logger.warning("Keyword merge returned no defects — emitting per-ticket issues")
            defects = self._singleton_defects(extractions)

        return defects

    def _merge_defects(self, extractions: list[dict], cluster_total: int) -> list[dict]:
        if not extractions:
            return []

        if self._fast_mode or not self._client:
            return self._fallback_merge(extractions, min_tickets=1)

        # Large clusters: merge in chunks so the model (and context window) are not overwhelmed.
        if len(extractions) > 45:
            partial: list[dict] = []
            for i in range(0, len(extractions), 40):
                chunk = extractions[i : i + 40]
                merged_chunk = self._merge_defects_llm(chunk, cluster_total)
                if merged_chunk:
                    partial.extend(merged_chunk)
                else:
                    partial.extend(self._fallback_merge(chunk, min_tickets=1))
            if len(partial) > 1:
                recombined = [
                    {
                        "ticket_id": tid,
                        "defect_hypothesis": d.get("issue_name", ""),
                        "complaint": d.get("issue_name", ""),
                    }
                    for d in partial
                    for tid in d.get("ticket_ids", [])
                ]
                return self._finalize_defects_small(recombined, cluster_total)
            return partial

        return self._finalize_defects_small(extractions, cluster_total)

    def _finalize_defects_small(self, extractions: list[dict], cluster_total: int) -> list[dict]:
        merged = self._merge_defects_llm(extractions, cluster_total)
        if merged:
            return merged
        return self._fallback_merge(extractions, min_tickets=1)

    def _merge_defects_llm(self, extractions: list[dict], cluster_total: int) -> list[dict]:
        prompt = (
            f"You received {len(extractions)} ticket defect extractions from the SAME cluster "
            f"({cluster_total} tickets total). Many describe the SAME product bug with different wording.\n\n"
            "MERGE duplicates into unique product defects. Each defect must:\n"
            "- Represent ONE actual product defect, user-reported failure, or missing capability\n"
            "- Include ticket_ids that share the same root issue (1 ticket is OK when it is a distinct issue)\n"
            "- There is NO minimum percentage of the cluster\n"
            "- Have issue_name: normalized defect title a PM would use in a bug tracker\n"
            "- Have root_cause: technical/product root cause IF inferable from evidence, else "
            '"Root cause not confirmed from ticket evidence."\n'
            "- Have evidence_summary: 1-2 sentences citing what tickets actually say\n\n"
            "Every ticket exists because a user reported a problem — do NOT return an empty array "
            "when extractions describe real issues.\n"
            "Do NOT split by module unless defects are genuinely different.\n"
            "Do NOT create catch-all buckets.\n"
            "Return JSON array: "
            '[{"issue_name": "...", "root_cause": "...", "ticket_ids": [ids], '
            '"evidence_summary": "...", "confidence": 0.0-1.0}]\n\n'
            f"Extractions:\n{json.dumps(extractions)}"
        )
        try:
            parsed = self._llm_json(prompt, temperature=0.2)
            if isinstance(parsed, list) and parsed:
                return parsed
            return []
        except Exception:
            logger.exception("Defect merge failed")
            self._disable_llm("OpenAI merge failed")
            return []

    def _build_intelligence_report(
        self,
        defect: dict,
        tickets: list[Ticket],
        cluster_total: int,
        share: float,
        *,
        fast: bool = False,
    ) -> dict:
        stats = self._compute_stats(tickets, cluster_total, share)
        enrichment = (
            self._enrich_defect(defect, tickets, stats)
            if not fast and self._client
            else self._static_enrichment(defect, tickets, stats)
        )

        resolution_summary = enrichment.get("developer_resolution_summary", "Resolution Unknown.")
        has_verified_resolution = enrichment.get("fix_status") in ("fixed", "verified", "deployed")
        regression_cases: list[str] = []

        if has_verified_resolution and resolution_summary != "Resolution Unknown.":
            regression_cases = enrichment.get("regression_test_cases") or []
            if not regression_cases and self._client:
                regression_cases = self._generate_regression_tests(defect, tickets, enrichment)

        return {
            **stats,
            "issue_name": defect.get("issue_name", "Unnamed defect"),
            "root_cause": defect.get("root_cause", enrichment.get("root_cause", "")),
            "evidence_summary": defect.get("evidence_summary", ""),
            "confidence": defect.get("confidence"),
            "ticket_ids": [t.id for t in tickets],
            "affected_module": enrichment.get("affected_module") or stats.get("affected_module", "Multiple"),
            "business_impact": enrichment.get("business_impact", ""),
            "fix_status": enrichment.get("fix_status", "unknown"),
            "developer_resolution_summary": resolution_summary,
            "regression_test_cases": regression_cases,
            "recurring": enrichment.get("recurring", stats.get("recurring", False)),
            "suggested_permanent_fix": enrichment.get("suggested_permanent_fix", ""),
            "suggested_product_improvement": enrichment.get("suggested_product_improvement", ""),
            "top_customer_complaints": enrichment.get("top_customer_complaints", stats.get("top_complaints", [])),
            "top_keywords": defect.get("top_keywords", []),
            "related_issues": enrichment.get("related_issues", []),
            "release_version_introduced": enrichment.get("release_version_introduced"),
            "release_version_fixed": enrichment.get("release_version_fixed"),
        }

    def _compute_stats(self, tickets: list[Ticket], cluster_total: int, share: float) -> dict:
        open_count = sum(
            1 for t in tickets
            if t.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED)
        )
        closed_count = len(tickets) - open_count
        dates_created = [t.created_at for t in tickets if t.created_at]
        dates_updated = [t.updated_at or t.created_at for t in tickets if (t.updated_at or t.created_at)]

        workshops: list[str] = []
        seen: set[str] = set()
        for t in tickets:
            w = (t.workshop_name or "").strip()
            if w and w.lower() not in ("unknown", "—", "-", "n/a") and w not in seen:
                seen.add(w)
                workshops.append(w)

        complaints: list[str] = []
        for t in tickets[:8]:
            if t.title:
                complaints.append(t.title[:120])

        modules: list[str] = []
        for t in tickets:
            m = infer_module_affected(t.title or "", t.description or "")
            if m and m not in modules:
                modules.append(m)

        hours_saved = sum(
            t.resolution_hours or t.dev_effort_hours or 0
            for t in tickets
            if t.status == TicketStatus.CLOSED
        )

        builds = [t.build_in for t in tickets if t.build_in]
        stages = [t.product_stage for t in tickets if t.product_stage]
        reopened = sum(1 for t in tickets if t.is_reopened)

        return {
            "ticket_count": len(tickets),
            "ticket_percentage": round(share * 100, 1),
            "first_seen": min(dates_created).strftime("%Y-%m-%d") if dates_created else None,
            "last_seen": max(dates_updated).strftime("%Y-%m-%d") if dates_updated else None,
            "open_count": open_count,
            "closed_count": closed_count,
            "workshops_affected": workshops[:15],
            "affected_module": " / ".join(modules[:3]) if modules else "Multiple Modules",
            "top_complaints": complaints[:5],
            "estimated_engineering_hours_saved": round(hours_saved, 1) if hours_saved else None,
            "recurring": reopened >= 2 or len(tickets) >= 5,
            "release_version_introduced": stages[0] if stages else None,
            "release_version_fixed": builds[0] if builds and closed_count > 0 else None,
        }

    def _enrich_defect(self, defect: dict, tickets: list[Ticket], stats: dict) -> dict:
        if not self._client:
            return self._static_enrichment(defect, tickets, stats)

        samples = []
        for t in tickets[:10]:
            samples.append({
                "id": t.id,
                "title": t.title,
                "description": (t.description or "")[:500],
                "status": t.status.value,
                "workshop": t.workshop_name,
                "build_in": t.build_in,
                "product_stage": t.product_stage,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            })

        prompt = (
            "Produce an engineering intelligence report for this MERGED product defect.\n\n"
            f"Issue: {defect.get('issue_name')}\n"
            f"Root cause hypothesis: {defect.get('root_cause')}\n"
            f"Evidence: {defect.get('evidence_summary')}\n"
            f"Stats: {json.dumps({k: stats[k] for k in ('ticket_count', 'open_count', 'closed_count', 'workshops_affected') if k in stats})}\n\n"
            "Sample tickets:\n"
            f"{json.dumps(samples)}\n\n"
            "Rules:\n"
            "- business_impact: concrete operational impact on workshops (not generic)\n"
            "- fix_status: one of open | in_progress | fixed | partial | unknown\n"
            "- developer_resolution_summary: ONLY if tickets explicitly mention a fix, deployment, or root cause resolution. "
            'Otherwise exactly: "Resolution Unknown."\n'
            "- regression_test_cases: MUST be empty array [] unless fix_status is fixed/verified AND resolution is documented\n"
            "- Never invent resolutions or test cases\n"
            "- Never write generic feature-level QA tests\n"
            "- recurring: true if same defect pattern appears across time/workshops\n"
            "- suggested_permanent_fix: engineering fix recommendation (even if resolution unknown)\n"
            "- suggested_product_improvement: UX/process improvement to prevent recurrence\n"
            "- related_issues: other defect names that might share root cause\n"
            "- release_version_introduced / release_version_fixed: only if mentioned in tickets, else null\n\n"
            "Return JSON object with those fields."
        )
        try:
            result = self._llm_json(prompt, temperature=0.25)
            if isinstance(result, dict):
                if result.get("developer_resolution_summary", "").strip().lower() in (
                    "", "unknown", "n/a", "not available"
                ):
                    result["developer_resolution_summary"] = "Resolution Unknown."
                    result["regression_test_cases"] = []
                return result
        except Exception:
            logger.exception("Defect enrichment failed")

        return {
            "business_impact": f"{stats['ticket_count']} tickets reported across workshops.",
            "fix_status": "unknown",
            "developer_resolution_summary": "Resolution Unknown.",
            "regression_test_cases": [],
            "recurring": stats.get("recurring", False),
        }

    @staticmethod
    def _static_enrichment(defect: dict, tickets: list[Ticket], stats: dict) -> dict:
        closed = stats.get("closed_count", 0)
        return {
            "business_impact": f"Affects {stats['ticket_count']} ticket(s) across {len(stats.get('workshops_affected', []))} workshop(s).",
            "fix_status": "fixed" if closed == stats["ticket_count"] and stats["ticket_count"] > 0 else "open",
            "developer_resolution_summary": (
                "Resolution Unknown." if closed < stats["ticket_count"] else "Closed per ticket status — details not extracted."
            ),
            "top_customer_complaints": stats.get("top_complaints", []),
            "recurring": stats.get("recurring", False),
            "regression_test_cases": [],
        }

    def _generate_regression_tests(
        self,
        defect: dict,
        tickets: list[Ticket],
        enrichment: dict,
    ) -> list[str]:
        if not self._client:
            return []

        samples = [{"title": t.title, "description": (t.description or "")[:300]} for t in tickets[:5]]
        prompt = (
            "Generate regression test cases ONLY because a verified resolution exists.\n\n"
            f"Defect: {defect.get('issue_name')}\n"
            f"Root cause: {defect.get('root_cause')}\n"
            f"Resolution: {enrichment.get('developer_resolution_summary')}\n\n"
            "Sample tickets that reported this defect:\n"
            f"{json.dumps(samples)}\n\n"
            "Write 2-4 REGRESSION tests that verify THIS SPECIFIC defect does not recur after the fix.\n"
            "Each test must reproduce the exact failure scenario from tickets, then assert correct behavior.\n"
            "Do NOT write generic module tests or feature walkthroughs.\n"
            'Return JSON array of strings.'
        )
        try:
            result = self._llm_json(prompt, temperature=0.3)
            if isinstance(result, list):
                return [str(c) for c in result if c]
        except Exception:
            logger.exception("Regression test generation failed")
        return []

    def _llm_json(self, prompt: str, temperature: float = 0.2):
        if self._fast_mode or not self._client:
            raise RuntimeError("fast_mode")
        try:
            resp = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": ANALYST_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                timeout=45,
            )
        except Exception as exc:
            msg = str(exc).lower()
            if "429" in msg or "quota" in msg or "rate_limit" in msg or "insufficient_quota" in msg:
                self._disable_llm("OpenAI quota/rate limit")
            raise
        content = resp.choices[0].message.content or "[]"
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(content)

    @staticmethod
    def _fallback_extraction(ticket: Ticket) -> dict:
        title = (ticket.title or "").strip()
        desc = (ticket.description or "").strip()
        hypothesis = title if title else (desc.split("\n")[0][:200] if desc else "Reported issue")
        return {
            "ticket_id": ticket.id,
            "defect_hypothesis": hypothesis,
            "complaint": title[:120] if title else hypothesis[:120],
            "resolution_mentioned": None,
            "module_hint": infer_module_affected(ticket.title or "", ticket.description or ""),
        }

    @staticmethod
    def _bucket_key(ext: dict) -> str:
        text = (ext.get("complaint") or ext.get("defect_hypothesis") or "").lower()
        text = re.sub(r"[^\w\s]", " ", text)
        words = [w for w in text.split() if len(w) > 2 and w not in KEYWORD_STOP]
        if words:
            return " ".join(sorted(set(words))[:6])
        return text[:40] or "reported issue"

    @staticmethod
    def _singleton_defects(extractions: list[dict]) -> list[dict]:
        defects: list[dict] = []
        seen: set[int] = set()
        for ext in extractions:
            tid = ext.get("ticket_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            name = (ext.get("complaint") or ext.get("defect_hypothesis") or "Reported issue").strip()
            defects.append({
                "issue_name": name[:120] or "Reported issue",
                "root_cause": "Root cause not confirmed from ticket evidence.",
                "ticket_ids": [tid],
                "evidence_summary": name[:200],
                "confidence": 0.35,
            })
        return defects

    @staticmethod
    def _fallback_merge(extractions: list[dict], min_tickets: int) -> list[dict]:
        buckets: dict[str, list[int]] = {}
        for ext in extractions:
            tid = ext.get("ticket_id")
            if not tid:
                continue
            bucket_key = ClusterAnalysisService._bucket_key(ext)
            buckets.setdefault(bucket_key, []).append(tid)

        defects = []
        for key, ids in buckets.items():
            unique_ids = list(dict.fromkeys(ids))
            if len(unique_ids) < min_tickets:
                continue
            label = key.title()[:80] or "Reported issue"
            defects.append({
                "issue_name": label,
                "root_cause": "Root cause not confirmed from ticket evidence.",
                "ticket_ids": unique_ids,
                "evidence_summary": f"{len(unique_ids)} ticket(s) report similar symptoms.",
                "confidence": 0.5 if len(unique_ids) > 1 else 0.35,
            })
        return defects

    def get_job(self, job_id: int) -> ClusterAnalysisJob | None:
        return (
            self.db.query(ClusterAnalysisJob)
            .filter(ClusterAnalysisJob.id == job_id)
            .first()
        )
