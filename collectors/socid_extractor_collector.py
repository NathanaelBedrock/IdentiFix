from __future__ import annotations
import httpx
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget

try:
    from socid_extractor import extract
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

PROFILE_URLS: dict[str, str] = {
    "twitter": "https://twitter.com/{username}",
    "reddit": "https://www.reddit.com/user/{username}",
    "github": "https://github.com/{username}",
    "instagram": "https://www.instagram.com/{username}/",
    "tiktok": "https://www.tiktok.com/@{username}",
}


class SocidExtractorCollector(BaseCollector):
    name = "socid_extractor"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return _AVAILABLE

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
            for platform, url_tpl in PROFILE_URLS.items():
                url = url_tpl.format(username=username)
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        extracted = extract(resp.text)
                        if extracted:
                            result.raw_data.setdefault("socid_extractor", {})[platform] = extracted
                except Exception:
                    continue
