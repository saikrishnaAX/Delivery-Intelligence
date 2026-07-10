"""Gmail SMTP email delivery."""

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailService:
    def __init__(self):
        self.user = settings.gmail_user.strip()
        self.password = settings.gmail_app_password.strip()
        self.from_name = settings.email_from_name or "Autorox Command Center"

    @property
    def configured(self) -> bool:
        return settings.email_configured

    def send_email(
        self,
        to_emails: list[str],
        subject: str,
        body_text: str,
        body_html: str | None = None,
        attachment: tuple[str, bytes] | None = None,
        cc_emails: list[str] | None = None,
    ) -> None:
        if not self.configured:
            raise RuntimeError("Gmail is not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        if not to_emails:
            raise ValueError("No recipients specified")

        cc = [e.strip() for e in (cc_emails or []) if e and e.strip()]

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.user}>"
        msg["To"] = ", ".join(to_emails)
        if cc:
            msg["Cc"] = ", ".join(cc)

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)

        if attachment:
            filename, data = attachment
            part = MIMEApplication(data, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()
                server.login(self.user, self.password)
                recipients = list(dict.fromkeys([*to_emails, *cc]))
                server.sendmail(self.user, recipients, msg.as_string())
        except Exception:
            logger.exception("Failed to send email to %s", to_emails)
            raise

    def release_notes_body(self, sprint_name: str, item_count: int, release_date: str) -> tuple[str, str]:
        text = (
            f"Hello,\n\n"
            f"Please find attached the release notes for {release_date}"
            f"{f' ({sprint_name})' if sprint_name else ''}. "
            f"This document covers {item_count} released item(s) across enhancements, "
            f"requirements, performance improvements, and bug fixes.\n\n"
            f"Regards,\n{self.from_name}\n"
        )
        html = (
            f"<p>Hello,</p>"
            f"<p>Please find attached the release notes for <strong>{release_date}</strong>"
            f"{f' ({sprint_name})' if sprint_name else ''}. "
            f"This document covers <strong>{item_count}</strong> released item(s) across "
            f"enhancements, requirements, performance improvements, and bug fixes.</p>"
            f"<p>Regards,<br>{self.from_name}</p>"
        )
        return text, html

    def archive_document_body(self, title: str, release_date: str) -> tuple[str, str]:
        text = (
            f"Hello,\n\n"
            f"Please find attached the release notes document: {title} ({release_date}).\n\n"
            f"Regards,\n{self.from_name}\n"
        )
        html = (
            f"<p>Hello,</p>"
            f"<p>Please find attached the release notes document: "
            f"<strong>{title}</strong> ({release_date}).</p>"
            f"<p>Regards,<br>{self.from_name}</p>"
        )
        return text, html

    def workshop_feedback_body(
        self, workshop_name: str, sprint_name: str, item_count: int
    ) -> tuple[str, str]:
        text = (
            f"Hello,\n\n"
            f"One week ago we released {sprint_name} for {workshop_name}. "
            f"Please collect customer feedback on the {item_count} item(s) delivered.\n\n"
            f"— {self.from_name}\n"
        )
        html = (
            f"<p>Hello,</p>"
            f"<p>One week ago we released <strong>{sprint_name}</strong> for "
            f"<strong>{workshop_name}</strong>. Please collect customer feedback on "
            f"<strong>{item_count}</strong> item(s) delivered.</p>"
            f"<p>— {self.from_name}</p>"
        )
        return text, html
