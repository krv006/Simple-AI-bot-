# bot/api_client.py
import logging
from typing import Any, Dict

import aiohttp

from .config import Settings

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.api_base_url.rstrip("/")
        self.auth_token = settings.api_auth_token

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = self.auth_token
        return headers

    async def post_json(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._build_headers()

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    logger.error("POST %s failed (%s): %s", url, resp.status, text)
                    raise RuntimeError(f"API error {resp.status}: {text}")
                try:
                    return await resp.json()
                except Exception:
                    logger.warning("Non-JSON response from %s: %s", url, text)
                    return {}

    async def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.post_json("/api/orders/", payload)

    async def create_dataset_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.post_json("/api/dataset/", payload)
