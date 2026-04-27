from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def fetch_homeowner_leads(
    zip_code: str,
    equity_min: int = 100_000,
    niche: str = "homeowner",
) -> list[dict[str, Any]]:
    headers = {}
    if settings.KJLE_API_KEY:
        headers["Authorization"] = f"Bearer {settings.KJLE_API_KEY}"
    url = f"{settings.KJLE_API_URL.rstrip('/')}/kjle/v1/leads"
    params = {"niche": niche, "equity_min": equity_min, "zip": zip_code}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        if r.status_code == 404:
            log.warning("kjle_no_leads", zip=zip_code)
            return []
        r.raise_for_status()
        data = r.json()
        return data.get("leads", data) if isinstance(data, dict) else data
