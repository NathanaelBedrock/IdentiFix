from __future__ import annotations
import httpx
from core.config import settings

DISCORD_API = "https://discord.com/api/v10"


class DiscordClient:
    def __init__(self):
        self._token = settings.discord_token

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise ValueError("DISCORD_TOKEN is not configured")
        return {"Authorization": f"Bot {self._token}"}

    async def get_user(self, user_id: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{DISCORD_API}/users/{user_id}", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def get_guild_member(self, guild_id: str, user_id: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{DISCORD_API}/guilds/{guild_id}/members/{user_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def search_guild_members(self, guild_id: str, query: str, limit: int = 10) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{DISCORD_API}/guilds/{guild_id}/members/search",
                params={"query": query, "limit": limit},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
