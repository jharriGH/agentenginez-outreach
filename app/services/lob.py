from typing import Any
import base64
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(f"{settings.LOB_API_KEY}:".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def addresses_within_radius(
    address_line1: str,
    city: str,
    state: str,
    zip_code: str,
    radius_miles: float = 0.5,
) -> list[dict[str, Any]]:
    """Lob USPS USAddressVerification + radius. Lob exposes a /us_autocompletions
    style endpoint for nearby addresses; here we use route+radius lookups.
    """
    if not settings.LOB_API_KEY:
        log.warning("lob_skipped_no_creds")
        return []
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://api.lob.com/v1/routes",
            headers=_auth_header(),
            params={"zip_codes[]": zip_code},
        )
        r.raise_for_status()
        return r.json().get("data", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def create_postcard(
    to_address: dict[str, Any],
    from_address: dict[str, Any],
    front: str,
    back: str,
    description: str = "AgentEnginez Postcard",
    size: str = "6x11",
) -> dict[str, Any]:
    if not settings.LOB_API_KEY:
        return {"id": None, "status": "skipped"}
    payload = {
        "description": description,
        "to": to_address,
        "from": from_address,
        "front": front,
        "back": back,
        "size": size,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.lob.com/v1/postcards",
            headers={**_auth_header(), "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def create_check(
    to_address: dict[str, Any],
    from_address: dict[str, Any],
    bank_account_id: str,
    amount: float,
    memo: str = "Referral reward",
    message: str = "Thanks for the referral!",
) -> dict[str, Any]:
    if not settings.LOB_API_KEY:
        return {"id": None, "status": "skipped"}
    payload = {
        "description": memo,
        "to": to_address,
        "from": from_address,
        "bank_account": bank_account_id,
        "amount": amount,
        "memo": memo,
        "message": message,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.lob.com/v1/checks",
            headers={**_auth_header(), "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()
