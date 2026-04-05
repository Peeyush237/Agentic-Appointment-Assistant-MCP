from __future__ import annotations

from typing import Any

import httpx


class MCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.server_url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result")

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._request("tools/list")
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        return result

    async def list_prompts(self) -> list[dict[str, Any]]:
        result = await self._request("prompts/list")
        return result.get("prompts", [])

    async def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("prompts/get", {"name": name, "arguments": arguments or {}})
