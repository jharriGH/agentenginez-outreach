from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class SupabaseClient:
    def __init__(self) -> None:
        self.base_url = f"{settings.SUPABASE_URL}/rest/v1"
        self.headers = {
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def select(
        self,
        table: str,
        params: dict[str, Any] | None = None,
        schema: str = "agentenginez",
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.base_url}/{table}",
                headers={**self.headers, "Accept-Profile": schema},
                params=params or {},
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def insert(
        self,
        table: str,
        payload: dict[str, Any] | list[dict[str, Any]],
        schema: str = "agentenginez",
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/{table}",
                headers={**self.headers, "Content-Profile": schema},
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def update(
        self,
        table: str,
        match: dict[str, Any],
        payload: dict[str, Any],
        schema: str = "agentenginez",
    ) -> list[dict[str, Any]]:
        params = {k: f"eq.{v}" for k, v in match.items()}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(
                f"{self.base_url}/{table}",
                headers={**self.headers, "Content-Profile": schema},
                params=params,
                json=payload,
            )
            r.raise_for_status()
            return r.json()


supabase = SupabaseClient()
