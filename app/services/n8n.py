from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class N8nClient:
    """n8n REST + webhook client.

    Public API uses /api/v1 with X-N8N-API-KEY header.
    GOAT rule: GET first, POST new only — never modify or delete existing workflows.
    """

    def __init__(self) -> None:
        self.base_url = settings.N8N_BASE_URL.rstrip("/")
        self.api_key = settings.N8N_API_KEY

    def _headers(self) -> dict[str, str]:
        return {
            "X-N8N-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def list_workflows(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.base_url}/api/v1/workflows",
                headers=self._headers(),
                params={"limit": 250},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("data", []) if isinstance(data, dict) else data

    async def find_workflow_by_name(self, name: str) -> dict[str, Any] | None:
        for wf in await self.list_workflows():
            if wf.get("name") == name:
                return wf
        return None

    async def create_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base_url}/api/v1/workflows",
                headers=self._headers(),
                json=payload,
            )
            if r.status_code >= 400:
                log.warning("n8n_create_error", status=r.status_code, body=r.text[:500])
                r.raise_for_status()
            return r.json()

    async def activate_workflow(self, workflow_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/api/v1/workflows/{workflow_id}/activate",
                headers=self._headers(),
            )
            if r.status_code >= 400:
                log.warning("n8n_activate_error", status=r.status_code, body=r.text[:300])
                r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=6))
    async def fire_webhook(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/webhook/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload)
            if r.status_code >= 400:
                log.warning("n8n_webhook_error", path=path, status=r.status_code, body=r.text[:300])
                r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {"status": "ok", "raw": r.text}


n8n = N8nClient()
