from __future__ import annotations
import httpx
from core.config import settings

REDDIT_API = "https://www.reddit.com"
REDDIT_OAUTH_API = "https://oauth.reddit.com"


class RedditClient:
    def __init__(self):
        self._client_id = settings.reddit_client_id
        self._client_secret = settings.reddit_client_secret
        self._user_agent = settings.reddit_user_agent
        self._access_token: str | None = None

    async def _ensure_token(self) -> None:
        if self._access_token:
            return
        if not (self._client_id and self._client_secret):
            raise ValueError("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not configured")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                headers={"User-Agent": self._user_agent},
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": self._user_agent,
        }

    async def get_user(self, username: str) -> dict:
        await self._ensure_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{REDDIT_OAUTH_API}/user/{username}/about",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_user_posts(self, username: str, limit: int = 25) -> dict:
        await self._ensure_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{REDDIT_OAUTH_API}/user/{username}/submitted",
                headers=self._headers(),
                params={"limit": limit, "sort": "new"},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_user_comments(self, username: str, limit: int = 25) -> dict:
        await self._ensure_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{REDDIT_OAUTH_API}/user/{username}/comments",
                headers=self._headers(),
                params={"limit": limit, "sort": "new"},
            )
            resp.raise_for_status()
            return resp.json()
