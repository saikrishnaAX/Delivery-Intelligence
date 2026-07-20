from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    database_url: str = "sqlite:///./delivery_intelligence.db"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Asana (read-only)
    asana_access_token: str = ""
    asana_workspace_gid: str = ""
    asana_type_field_name: str = "Type"
    asana_released_section_name: str = "Released(With Release Notes)"
    asana_sprint_section_name: str = "Prioritized"

    # Jira (read-only) — separate project from Asana
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    use_mock_data: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    api_prefix: str = "/api/v1"
    auto_sync_enabled: bool = True
    auto_sync_interval_minutes: int = 10
    auto_sync_ui_poll_seconds: int = 60
    asana_webhook_target_url: str = ""

    # Google Sheets (service account — share spreadsheet with client_email)
    google_service_account_file: str = ""
    google_service_account_json: str = ""

    # Gmail SMTP (release notes + workshop reminders + status-move digests)
    gmail_user: str = ""
    gmail_app_password: str = ""
    email_from_name: str = "Autorox Command Center"
    support_head_email: str = ""

    # Status-move alerts (Asana column changes during sync)
    status_move_notify_enabled: bool = True
    # Google Chat incoming webhook URL (Spaces → Apps & integrations → Webhooks)
    google_chat_webhook_url: str = ""
    # Comma-separated tech emails only; empty = no email (never uses SUPPORT_HEAD_EMAIL)
    status_move_email_to: str = ""
    # If true, only notify moves into Testing / Done / Released (quieter Chat)
    status_move_highlight_only: bool = False
    # New Jira Bug/Sub-task under a parent → same Google Chat space
    jira_bug_notify_enabled: bool = True

    # CEO Intelligence
    ai_adoption_date: str = "2026-05-01"
    ceo_email: str = "vijay@autorox.co"
    ceo_report_auto_enabled: bool = False
    ceo_report_frequency: str = "weekly"  # weekly | monthly | 6months
    # Weekly CEO email (IST): brief refreshed Monday 5 PM with daily issue intel; send Tuesday
    ceo_weekly_send_weekday: int = 1  # Tuesday
    ceo_weekly_send_hour_ist: int = 8

    # Daily Issue Intelligence + Cursor enrich (IST) — urgent recurring issues
    issue_intelligence_daily_enabled: bool = True
    issue_intelligence_daily_hour_ist: int = 17  # 5 PM

    # Cursor agent analysis (replaces OpenAI for issue enrich + CEO narrative)
    cursor_api_key: str = ""
    cursor_model: str = "composer-2.5"
    cursor_analysis_enabled: bool = True
    cursor_issue_enrich_limit: int = 12

    # Cluster deep analysis — keyword-first (fast); set use_openai=true for optional AI refine
    cluster_analysis_batch_size: int = 12
    cluster_analysis_ticket_cap: int = 1000
    cluster_analysis_use_openai: bool = False

    # Stored release note DOCX files
    release_notes_storage_dir: str = "data/release_notes"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def asana_configured(self) -> bool:
        return bool(self.asana_access_token and self.asana_workspace_gid)

    @property
    def jira_configured(self) -> bool:
        return bool(
            self.jira_base_url.strip()
            and self.jira_email.strip()
            and self.jira_api_token.strip()
            and self.jira_project_key.strip()
        )

    @property
    def email_configured(self) -> bool:
        return bool(self.gmail_user.strip() and self.gmail_app_password.strip())

    @property
    def google_chat_configured(self) -> bool:
        return bool(self.google_chat_webhook_url.strip())

    @property
    def status_move_email_recipients(self) -> list[str]:
        """Tech-team digests only — never falls back to SUPPORT_HEAD_EMAIL / Prasad."""
        return [e.strip() for e in self.status_move_email_to.split(",") if e.strip()]

    @property
    def cursor_configured(self) -> bool:
        return bool(self.cursor_api_key.strip() and self.cursor_analysis_enabled)


def get_settings() -> Settings:
    """Load settings from environment / .env (no cache — picks up .env edits)."""
    return Settings()