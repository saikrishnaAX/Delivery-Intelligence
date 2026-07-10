# Live Integrations Setup Guide

This guide walks you through connecting **Asana** (tickets by project) and **Jira** (separate project) for live dashboard data.

---

## 1. Asana — Personal Access Token

1. Open **[Asana Developer Console](https://app.asana.com/0/my-apps)**
2. Click **Create new token** (or use an existing Personal Access Token)
3. Copy the token → set as `ASANA_ACCESS_TOKEN` in `.env`

> The token is read-only if you only grant read scopes. Never commit `.env` to git.

---

## 2. Asana — Workspace GID

**Option A — Browser (quick)**

1. Log into Asana
2. Open your workspace
3. Use the API explorer or run:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" https://app.asana.com/api/1.0/workspaces
```

4. Copy the `"gid"` of your workspace → `ASANA_WORKSPACE_GID`

**Option B — From project URL**

When viewing a project, the URL often contains IDs you can cross-reference via the projects list endpoint.

---

## 3. Asana — Project selection in the dashboard

After configuring `.env`:

1. Set `USE_MOCK_DATA=false`
2. Restart the backend
3. Open the dashboard — the **project dropdown** loads all non-archived projects from your workspace
4. Select the project you want to analyze
5. Click **Sync** to pull tasks from that Asana project

All dashboards filter by the selected project.

---

## 4. Asana — `Type` custom field (Support category)

Your support team uses a custom field named **`Type`**.

During sync, the app reads this field and maps it to `support_category`:

| Asana Type value | Dashboard category |
|------------------|-------------------|
| Bug | bug |
| Enhancement / Feature | enhancement |
| Configuration / Config | configuration |
| Knowledge Gap / Question | knowledge_gap |
| Duplicate | duplicate |

The AI independently classifies each task into `ai_category` for the **Accuracy** dashboard.

If your field name differs, set `ASANA_TYPE_FIELD_NAME` in `.env`.

**Module mapping:** Asana **section** names within the project map to product modules (heat map).

---

## 5. Jira — API token & project key

Jira runs as a **separate project** (not linked per Asana task).

### API token

1. Go to **[Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)**
2. **Create API token**
3. Set in `.env`:
   - `JIRA_EMAIL` = your Atlassian login email
   - `JIRA_API_TOKEN` = the token you created
   - `JIRA_BASE_URL` = `https://YOUR-ORG.atlassian.net`

### Project key

1. Open any issue in your Jira project
2. The key prefix is the project key (e.g. `DEL-123` → `DEL`)
3. Set `JIRA_PROJECT_KEY=DEL` in `.env`

On **Sync**, Jira issues from that project are imported into the Jira dashboard for the currently selected Asana project context.

---

## 6. Complete `.env` example (live mode)

```env
DATABASE_URL=sqlite:///./delivery_intelligence.db

USE_MOCK_DATA=false

ASANA_ACCESS_TOKEN=2/1234567890:abcdef...
ASANA_WORKSPACE_GID=1234567890123456
ASANA_TYPE_FIELD_NAME=Type

JIRA_BASE_URL=https://acme.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=your_atlassian_api_token
JIRA_PROJECT_KEY=DEL

OPENAI_API_KEY=sk-...   # optional, improves AI assistant

CORS_ORIGINS=http://localhost:5173
```

---

## 7. First-time live setup steps

```bash
# 1. Copy env file
cp .env.example .env
# Edit .env with your credentials

# 2. Remove old mock database (schema changed)
rm backend/delivery_intelligence.db   # Windows: del backend\delivery_intelligence.db

# 3. Start backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. Start frontend
cd frontend
npm run dev
```

5. Open http://localhost:5173
6. Pick your Asana project from the dropdown
7. Click **Sync**
8. Dashboards populate with live data

---

## 8. API endpoints (for reference)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/integrations/status` | Check Asana/Jira config |
| GET | `/api/v1/projects` | List Asana projects |
| POST | `/api/v1/sync/{project_gid}` | Sync Asana tasks + Jira issues |
| GET | `/api/v1/executive?project_gid=...` | Project-scoped metrics |

Interactive docs: http://localhost:8000/docs

---

## 9. Troubleshooting

| Issue | Fix |
|-------|-----|
| Empty project dropdown | Check `ASANA_ACCESS_TOKEN` and `ASANA_WORKSPACE_GID` |
| Sync returns 401 | Regenerate Asana token or Jira API token |
| Type field not mapping | Confirm custom field is exactly `Type` or update `ASANA_TYPE_FIELD_NAME` |
| Jira sync fails | Verify `JIRA_PROJECT_KEY` and that your account can view the project |
| Still seeing mock data | Set `USE_MOCK_DATA=false` and delete the SQLite DB file |
| Sync button disabled | Mock mode is on, or Asana is not configured |
