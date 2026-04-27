from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def initiate_ava_call(
    to_number: str,
    script_vars: dict[str, Any],
    trunk: str = "twilio",
    from_number: str | None = None,
) -> dict[str, Any]:
    """POST to Asterisk ARI to originate an outbound AVA call."""
    auth = (settings.ASTERISK_ARI_USER, settings.ASTERISK_ARI_PASS)
    payload = {
        "endpoint": f"PJSIP/{to_number.lstrip('+')}@{trunk}",
        "extension": "s",
        "context": "ava-outbound",
        "priority": 1,
        "callerId": from_number or settings.TWILIO_FROM_NUMBER,
        "variables": {f"AVA_{k.upper()}": str(v) for k, v in script_vars.items()},
    }
    url = f"http://{settings.ASTERISK_VPS_IP}:8088/ari/channels"
    async with httpx.AsyncClient(timeout=30, auth=auth) as client:
        r = await client.post(url, json=payload)
        if r.status_code >= 400:
            log.warning("ava_call_failed", status=r.status_code, body=r.text[:200])
            r.raise_for_status()
        return r.json()
