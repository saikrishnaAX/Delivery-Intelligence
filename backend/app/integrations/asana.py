"""Read-only Asana integration."""

import httpx
from app.config import get_settings

settings = get_settings()
ASANA_API = "https://app.asana.com/api/1.0"

TASK_FIELDS = (
    "name,notes,completed,assignee.name,created_by.name,created_by.email,created_at,completed_at,modified_at,"
    "custom_fields,custom_fields.name,custom_fields.display_value,custom_fields.enum_value,"
    "custom_fields.text_value,custom_fields.number_value,custom_fields.multi_enum_values,tags,"
    "memberships,memberships.section.name,permalink_url,due_on"
)


class AsanaClient:
    def __init__(self):
        self.token = settings.asana_access_token
        self.workspace_gid = settings.asana_workspace_gid
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return settings.asana_configured

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def _http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0))
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict | None = None) -> dict:
        client = await self._http_client()
        resp = await client.get(f"{ASANA_API}{path}", headers=self._headers(), params=params or {})
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, payload: dict) -> dict:
        client = await self._http_client()
        resp = await client.post(
            f"{ASANA_API}{path}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def list_webhooks(self, workspace_gid: str | None = None) -> list[dict]:
        if not self.is_configured:
            return []
        ws = workspace_gid or self.workspace_gid
        data = await self._get("/webhooks", {"workspace": ws})
        return data.get("data", [])

    async def create_webhook(self, resource_gid: str, target_url: str) -> dict:
        data = await self._post("/webhooks", {
            "data": {
                "resource": resource_gid,
                "target": target_url,
            },
        })
        return data.get("data", {})

    async def fetch_task_project_gids(self, task_gid: str) -> list[str]:
        if not self.is_configured:
            return []
        data = await self._get(f"/tasks/{task_gid}", {"opt_fields": "projects,projects.gid"})
        task = data.get("data") or {}
        return [str(p["gid"]) for p in (task.get("projects") or []) if p.get("gid")]

    async def fetch_workspaces(self) -> list[dict]:
        if not self.is_configured:
            return []
        data = await self._get("/workspaces")
        return data.get("data", [])

    async def fetch_projects(self, workspace_gid: str | None = None) -> list[dict]:
        if not self.is_configured:
            return []
        ws = workspace_gid or self.workspace_gid
        projects: list[dict] = []
        offset = None
        while True:
            params: dict = {"workspace": ws, "limit": 100, "opt_fields": "name,archived,color,permalink_url"}
            if offset:
                params["offset"] = offset
            data = await self._get("/projects", params)
            projects.extend(data.get("data", []))
            next_page = data.get("next_page") or {}
            offset = next_page.get("offset")
            if not offset:
                break
        return [p for p in projects if not p.get("archived")]

    async def fetch_project_tasks(self, project_gid: str) -> list[dict]:
        if not self.is_configured:
            return []
        tasks: list[dict] = []
        offset = None
        while True:
            params: dict = {"limit": 100, "opt_fields": TASK_FIELDS}
            if offset:
                params["offset"] = offset
            data = await self._get(f"/projects/{project_gid}/tasks", params)
            tasks.extend(data.get("data", []))
            next_page = data.get("next_page") or {}
            offset = next_page.get("offset")
            if not offset:
                break
        return tasks

    async def fetch_project_sections(self, project_gid: str) -> list[dict]:
        """Board sections for a project (includes Prioritized, Developing, etc.)."""
        if not self.is_configured:
            return []
        sections: list[dict] = []
        offset = None
        while True:
            params: dict = {"limit": 100, "opt_fields": "name,created_at"}
            if offset:
                params["offset"] = offset
            data = await self._get(f"/projects/{project_gid}/sections", params)
            sections.extend(data.get("data", []))
            next_page = data.get("next_page") or {}
            offset = next_page.get("offset")
            if not offset:
                break
        return sections

    async def fetch_section_tasks(self, section_gid: str) -> list[dict]:
        """Tasks in board order for a section."""
        if not self.is_configured:
            return []
        tasks: list[dict] = []
        offset = None
        while True:
            params: dict = {"limit": 100, "opt_fields": "gid"}
            if offset:
                params["offset"] = offset
            data = await self._get(f"/sections/{section_gid}/tasks", params)
            tasks.extend(data.get("data", []))
            next_page = data.get("next_page") or {}
            offset = next_page.get("offset")
            if not offset:
                break
        return tasks

    async def fetch_task(self, task_gid: str) -> dict | None:
        if not self.is_configured:
            return None
        try:
            data = await self._get(f"/tasks/{task_gid}", {"opt_fields": TASK_FIELDS})
            return data.get("data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def fetch_task_stories(self, task_gid: str) -> list[dict]:
        if not self.is_configured:
            return []
        params = {
            "opt_fields": (
                "resource_subtype,created_at,text,"
                "new_section.name,old_section.name,target.name,created_by.name"
            ),
        }
        data = await self._get(f"/tasks/{task_gid}/stories", params)
        return data.get("data", [])

    async def fetch_task_attachments(self, task_gid: str) -> list[dict]:
        """Attachments include native Jira Cloud links (resource_subtype=external)."""
        if not self.is_configured:
            return []
        params = {
            "opt_fields": "name,resource_subtype,view_url,permanent_url,connected_to_app,host",
        }
        data = await self._get(f"/tasks/{task_gid}/attachments", params)
        attachments = data.get("data", [])
        detailed: list[dict] = []
        for att in attachments:
            if att.get("resource_subtype") != "external" and not att.get("view_url"):
                detailed.append(att)
                continue
            if att.get("view_url"):
                detailed.append(att)
                continue
            gid = att.get("gid")
            if not gid:
                continue
            try:
                full = await self._get(f"/attachments/{gid}", params)
                detailed.append(full.get("data") or att)
            except httpx.HTTPStatusError:
                detailed.append(att)
        return detailed
