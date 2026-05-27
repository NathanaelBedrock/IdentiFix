from __future__ import annotations
import httpx
from core.config import settings

TWITTER_API = "https://api.twitter.com/2"


class TwitterClient:
    def __init__(self):
        self._token = settings.twitter_bearer_token

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise ValueError("TWITTER_BEARER_TOKEN is not configured")
        return {"Authorization": f"Bearer {self._token}"}

    async def get_user_by_username(self, username: str) -> dict:
        params = {
            "user.fields": "id,name,username,description,public_metrics,profile_image_url,location,url,verified,created_at",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TWITTER_API}/users/by/username/{username}",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_user_tweets(self, user_id: str, max_results: int = 10) -> dict:
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics,entities",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TWITTER_API}/users/{user_id}/tweets",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_user_followers(self, user_id: str, max_results: int = 100) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TWITTER_API}/users/{user_id}/followers",
                headers=self._headers(),
                params={"max_results": max_results, "user.fields": "username,name"},
            )
            resp.raise_for_status()
            return resp.json()
