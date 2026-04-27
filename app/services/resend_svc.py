from typing import Any
import resend

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def send_email(to: str, subject: str, html: str, from_email: str = "hello@agentenginez.com") -> dict[str, Any]:
    if not settings.RESEND_API_KEY:
        log.warning("resend_skipped_no_creds", to=to)
        return {"id": None, "status": "skipped"}
    resend.api_key = settings.RESEND_API_KEY
    res = resend.Emails.send(
        {"from": from_email, "to": to, "subject": subject, "html": html}
    )
    log.info("resend_sent", to=to, id=res.get("id"))
    return res
