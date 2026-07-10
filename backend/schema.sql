-- Autorox AI Delivery Intelligence — Database Schema Reference
-- Auto-created by SQLAlchemy on startup; this file is for documentation.

CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'closed', 'blocked');
CREATE TYPE ticket_category AS ENUM ('bug', 'enhancement', 'configuration', 'knowledge_gap', 'duplicate');
CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'critical');

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tier VARCHAR(50) DEFAULT 'standard',
    industry VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE modules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    product_area VARCHAR(100)
);

CREATE TABLE issue_clusters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    ai_summary TEXT,
    ticket_count INTEGER DEFAULT 0,
    severity VARCHAR(50) DEFAULT 'medium',
    module_id INTEGER REFERENCES modules(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    asana_gid VARCHAR(50) UNIQUE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status ticket_status DEFAULT 'open',
    support_category ticket_category,
    ai_category ticket_category,
    priority ticket_priority DEFAULT 'medium',
    module_id INTEGER REFERENCES modules(id),
    customer_id INTEGER REFERENCES customers(id),
    assignee VARCHAR(255),
    reporter VARCHAR(255),
    is_critical_blocker BOOLEAN DEFAULT FALSE,
    is_reopened BOOLEAN DEFAULT FALSE,
    sla_hours INTEGER DEFAULT 48,
    sla_met BOOLEAN,
    resolution_hours FLOAT,
    cluster_id INTEGER REFERENCES issue_clusters(id),
    jira_key VARCHAR(50),
    tags JSONB DEFAULT '[]',
    asana_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

CREATE TABLE jira_issues (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER UNIQUE REFERENCES tickets(id),
    jira_key VARCHAR(50) UNIQUE NOT NULL,
    summary VARCHAR(500),
    status VARCHAR(100),
    issue_type VARCHAR(100),
    sprint_name VARCHAR(255),
    sprint_state VARCHAR(50),
    story_points FLOAT,
    assignee VARCHAR(255),
    jira_url VARCHAR(500),
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ai_insights (
    id SERIAL PRIMARY KEY,
    page VARCHAR(100) NOT NULL,
    insight_type VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    severity VARCHAR(50) DEFAULT 'info',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE executive_summaries (
    id SERIAL PRIMARY KEY,
    summary TEXT NOT NULL,
    key_metrics JSONB DEFAULT '{}',
    recommendations JSONB DEFAULT '[]',
    generated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX ix_tickets_status ON tickets(status);
CREATE INDEX ix_tickets_priority ON tickets(priority);
CREATE INDEX ix_tickets_created_at ON tickets(created_at);
CREATE INDEX ix_tickets_module_id ON tickets(module_id);
CREATE INDEX ix_tickets_customer_id ON tickets(customer_id);
CREATE INDEX ix_tickets_cluster_id ON tickets(cluster_id);
CREATE INDEX ix_ai_insights_page ON ai_insights(page);
