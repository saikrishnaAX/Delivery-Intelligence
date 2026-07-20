"""Read-only Jira integration."""

import httpx
import base64
from app.config import get_settings

class JiraClient:
    def __init__(self):
        self._refresh_settings()

    def _refresh_settings(self) -> None:
        settings = get_settings()
        self.base_url = settings.jira_base_url.rstrip("/")
        self.email = settings.jira_email
        self.token = settings.jira_api_token
        self.default_project_key = settings.jira_project_key

    @property
    def is_configured(self) -> bool:
        self._refresh_settings()
        return get_settings().jira_configured

    def _auth_header(self) -> dict:
        creds = base64.b64encode(f"{self.email}:{self.token}".encode()).decode()
        return {"Authorization": f"Basic {creds}", "Accept": "application/json"}

    async def fetch_project_issues(self, project_key: str | None = None, max_results: int = 200) -> list[dict]:
        self._refresh_settings()
        if not self.is_configured:
            return []
        key = project_key or self.default_project_key
        jql = f"project = {key} ORDER BY updated DESC"
        issues: list[dict] = []
        next_page_token: str | None = None
        page_size = min(100, max_results)

        async with httpx.AsyncClient(timeout=60.0) as client:
            while len(issues) < max_results:
                payload: dict = {
                    "jql": jql,
                    "maxResults": min(page_size, max_results - len(issues)),
                    "fields": [
                        "summary",
                        "status",
                        "issuetype",
                        "assignee",
                        "created",
                        "updated",
                        "parent",
                        "description",
                    ],
                }
                if next_page_token:
                    payload["nextPageToken"] = next_page_token

                resp = await client.post(
                    f"{self.base_url}/rest/api/3/search/jql",
                    headers={**self._auth_header(), "Content-Type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                body = resp.json()
                batch = body.get("issues", [])
                issues.extend(batch)
                next_page_token = body.get("nextPageToken")
                if not batch or not next_page_token:
                    break

        return issues[:max_results]

    async def fetch_issue(self, issue_key: str) -> dict | None:
        if not self.is_configured:
            return None
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/3/issue/{issue_key}",
                headers=self._auth_header(),
                params={
                    "fields": "summary,status,issuetype,assignee,parent,description,project,created,updated",
                },
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    async def register_webhook(self, target_url: str, project_key: str | None = None) -> dict:
        """Register a dynamic Jira Cloud webhook (expires ~30 days; refreshed on startup)."""
        self._refresh_settings()
        if not self.is_configured:
            raise RuntimeError("Jira is not configured")
        key = project_key or self.default_project_key
        jql = f"project = {key}" if key else "project is not EMPTY"
        payload = {
            "url": target_url,
            "webhooks": [
                {
                    "events": ["jira:issue_created", "jira:issue_updated"],
                    "jqlFilter": jql,
                }
            ],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/rest/api/3/webhook",
                headers={**self._auth_header(), "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def list_webhooks(self) -> list[dict]:
        self._refresh_settings()
        if not self.is_configured:
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/3/webhook",
                headers=self._auth_header(),
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            body = resp.json()
            if isinstance(body, list):
                return body
            return body.get("values") or body.get("webhooks") or []

    async def delete_webhook(self, webhook_id: int | str) -> None:
        self._refresh_settings()
        if not self.is_configured:
            return
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{self.base_url}/rest/api/3/webhook/{webhook_id}",
                headers=self._auth_header(),
            )
            if resp.status_code not in (200, 204, 404):
                resp.raise_for_status()

    async def fetch_active_sprints(self, board_id: int | None = None) -> list[dict]:
        """Fetch sprints if board_id provided; otherwise return empty."""
        if not self.is_configured or not board_id:
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint",
                headers=self._auth_header(),
                params={"state": "active,future"},
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("values", [])
