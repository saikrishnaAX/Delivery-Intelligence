# Autorox AI Delivery Intelligence Dashboard

Enterprise-grade AI-powered delivery analytics platform that reads Asana tickets and Jira issues in **read-only** mode and provides AI-driven insights across delivery operations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                     │
│  Tailwind · Shadcn UI · Recharts · Dark/Light Mode          │
├─────────────────────────────────────────────────────────────┤
│                    FastAPI Backend                           │
│  Analytics · AI Service · Asana/Jira Integrations           │
├─────────────────────────────────────────────────────────────┤
│                    PostgreSQL Database                         │
│  Tickets · Clusters · Customers · Jira · AI Insights      │
└─────────────────────────────────────────────────────────────┘
```

## Features

| Dashboard | Description |
|-----------|-------------|
| **Executive** | KPIs, trends, auto-generated AI executive summary |
| **Classification** | Bug, Enhancement, Configuration, Knowledge Gap, Duplicate |
| **Clustering** | AI-grouped similar issue clusters |
| **Heat Map** | Ticket distribution by product module |
| **Support Accuracy** | Support vs AI classification comparison |
| **Workflow Blockers** | Critical business-stopping issues |
| **Customer Pain** | Top customers by pain score and recurring issues |
| **Jira Integration** | Linked issues, sprints, velocity (read-only) |
| **Resolution Analytics** | SLA compliance, resolution trends, reopened tickets |
| **AI Assistant** | Natural language querying over ticket data |

Every page includes an **AI Insights panel** with contextual recommendations.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.12+ (optional, for local backend dev)

### 1. Start Backend

Copy environment file:

```bash
cp .env.example .env
```

Install backend dependencies and run:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API uses **SQLite by default** for local development and auto-seeds 200 sample tickets on first startup when `USE_MOCK_DATA=true`.

For production, set `DATABASE_URL` to PostgreSQL and run `docker compose up -d postgres`.

### 2. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

### Full Docker Stack

```bash
docker compose up --build
```

## Live Integrations (Asana + Jira)

**Full setup guide:** see [INTEGRATIONS.md](./INTEGRATIONS.md)

Quick summary:
1. Copy `.env.example` → `.env` and fill in credentials
2. Set `USE_MOCK_DATA=false`
3. Delete `backend/delivery_intelligence.db` (fresh schema)
4. Restart backend, select an **Asana project** from the dropdown, click **Sync**

| Credential | Where to get it |
|------------|-----------------|
| `ASANA_ACCESS_TOKEN` | [Asana Developer Console](https://app.asana.com/0/my-apps) |
| `ASANA_WORKSPACE_GID` | `GET /workspaces` API or workspace settings |
| `JIRA_API_TOKEN` | [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `JIRA_PROJECT_KEY` | Issue key prefix (e.g. `DEL` from `DEL-123`) |

Support category comes from Asana custom field **`Type`**. Jira issues load from a separate Jira project.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/integrations/status` | Integration config status |
| GET | `/api/v1/projects` | List Asana projects |
| POST | `/api/v1/sync/{project_gid}` | Sync Asana + Jira for project |
| GET | `/api/v1/executive?project_gid=` | Executive dashboard (project-scoped) |
| GET | `/api/v1/executive/summary` | AI executive summary |
| GET | `/api/v1/tickets` | Paginated ticket list |
| GET | `/api/v1/classification` | Category breakdown |
| GET | `/api/v1/clustering` | Issue clusters |
| GET | `/api/v1/heatmap` | Module heat map |
| GET | `/api/v1/accuracy` | Support accuracy |
| GET | `/api/v1/blockers` | Workflow blockers |
| GET | `/api/v1/customers` | Customer pain analysis |
| GET | `/api/v1/jira` | Jira linked issues |
| GET | `/api/v1/resolution` | Resolution analytics |
| GET | `/api/v1/insights/{page}` | Page-specific AI insights |
| POST | `/api/v1/assistant/chat` | AI assistant chat |

Interactive API docs: **http://localhost:8000/docs**

## Integrations (Read-Only)

### Asana

Set in `.env`:
```
ASANA_ACCESS_TOKEN=your_token
ASANA_WORKSPACE_GID=your_workspace_gid
USE_MOCK_DATA=false
```

### Jira

Set in `.env`:
```
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your_token
```

### OpenAI

```
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o-mini
```

Without an API key, the AI assistant uses intelligent mock responses based on live analytics data.

## Database Schema

Core tables: `customers`, `modules`, `tickets`, `issue_clusters`, `jira_issues`, `ai_insights`, `executive_summaries`

See `backend/schema.sql` for the full DDL reference.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/routes.py          # API endpoints
│   │   ├── integrations/          # Asana & Jira clients
│   │   ├── models/                # SQLAlchemy models
│   │   ├── schemas/               # Pydantic schemas
│   │   ├── services/              # Analytics & AI logic
│   │   └── seed/mock_data.py      # Sample data generator
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/            # UI, charts, layout
│       ├── pages/                 # Dashboard pages
│       ├── hooks/                 # Theme, API hooks
│       └── lib/                   # Utils, API client
├── docker-compose.yml
└── .env.example
```

## Design System

- **Shadcn UI** components with design tokens
- **Dark/Light mode** with system preference detection
- Consistent spacing, typography, card, and button patterns
- Responsive layouts with mobile-friendly charts
- AI Insights panel on every dashboard page

## License

Proprietary — Autorox AI Command Center
