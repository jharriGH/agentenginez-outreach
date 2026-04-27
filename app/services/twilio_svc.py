from typing import Any
from twilio.rest import Client

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _client() -> Client:
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_sms(to: str, body: str) -> dict[str, Any]:
    if not settings.TWILIO_ACCOUNT_SID:
        log.warning("twilio_skipped_no_creds", to=to)
        return {"sid": None, "status": "skipped"}
    msg = _client().messages.create(
        from_=settings.TWILIO_FROM_NUMBER, to=to, body=body
    )
    log.info("twilio_sms_sent", to=to, sid=msg.sid)
    return {"sid": msg.sid, "status": msg.status}
